"""The LLM support agent (TSD-016, T-301): the model writes the reply, the harness plans.

``LlmAgent`` implements ``SupportAgent`` behind the same seam as the ``TemplateAgent``. The split
is deliberate (decision 10, DESIGN 4.0): a *planner* (the TemplateAgent by default) decides which
tools run, which payment is in focus and whether the customer asked for a write, by literal rules,
so a model can never name a tool, a customer or an action. Only once the verified facts are in
hand does the model get one call to say them in the customer's language. Whatever it writes still
goes through the verifier cascade; the prompt asks for grounding, the verifier enforces it.

Failures are not papered over: a provider error or a draft that breaks a guard raises, the hub
escalates it as AGENT-ERROR, and the evaluation therefore never credits the model with a reply the
template wrote. The agent keeps every response it received so the runner can sum tokens and
latency per case.
"""

from __future__ import annotations

import json
import re
from typing import Any

from calvino.hub.agent import AgentDraft, AgentRequest, SupportAgent
from calvino.hub.prompts import PromptSet, load_prompts
from calvino.hub.state import HubStage
from calvino.hub.template_agent import TemplateAgent
from calvino.llm import ChatClient, ChatRequest, ChatResponse, Message, MessageRole, ReasoningEffort
from calvino.llm.contracts import Role

# A customer reply is two or three sentences; anything longer is a model rambling or restating
# the record, and a long answer has more room to carry an ungrounded claim.
MAX_REPLY_CHARS = 700

# A reasoning model spends its budget thinking before it writes. Measured on Hetzner (2026-10-04):
# one three-sentence reply cost 3,064 completion tokens, and a 2,048 budget ended with finish
# reason "length" and no reply at all (LLM-TRUNCATED). 8,192 leaves headroom; the client still
# raises LlmTruncated if a harder prompt runs out, which the hub escalates as AGENT-ERROR.
COMPLETION_BUDGET = 8192

# Fixed so a repeated evaluation run is comparable (T-303); the temperature is 0 for the same
# reason. Providers honour a seed on a best-effort basis, so identical text is not guaranteed.
DEFAULT_SEED = 7

# Markup that means the model answered in a tool-call or code dialect, not in prose.
_NOT_PROSE = re.compile(r"```|<tool_call|<function|\"tool_calls\"|\"function_call\"", re.IGNORECASE)

# The tool results each stage may cite: nothing else is put in the prompt, so the model sees only
# facts this session's tools returned (AgentRequest already holds nothing else).
_WRITE_TOOLS = frozenset({"request_cancellation", "retry_payment"})

_STAGE_TOOLS = {
    HubStage.EXPLAIN.value: ("get_entry_detail",),
    HubStage.ACT.value: (
        "get_entry_detail",
        "request_cancellation",
        "retry_payment",
        "get_payment_status",
    ),
    HubStage.FOLLOW_UP.value: ("get_investigation_status",),
}


class AgentOutputError(RuntimeError):
    """The model's draft broke a guard (empty, too long, not prose); the hub escalates it."""


class LlmAgent:
    """Writes the customer's reply with a language model; implements ``SupportAgent``."""

    def __init__(
        self,
        client: ChatClient,
        *,
        planner: SupportAgent | None = None,
        prompts: PromptSet | None = None,
        seed: int | None = DEFAULT_SEED,
    ) -> None:
        self._client = client
        self._planner = planner if planner is not None else TemplateAgent()
        self._prompts = prompts if prompts is not None else load_prompts()
        self._seed = seed
        self.responses: list[ChatResponse] = []

    @property
    def prompt_version(self) -> str:
        return self._prompts.version

    def draft(self, request: AgentRequest) -> AgentDraft:
        planned = self._planner.draft(request)
        stage = self._effective_stage(request)
        if planned.tool_calls or not self._model_writes(request, stage):
            # A tool plan, or a fixed reply with no payload to cite (nothing to write about):
            # the model is not involved.
            return planned
        response = self._client.complete(self._chat_request(request, stage))
        self.responses.append(response)
        return AgentDraft(text=self._guard(response))

    def drain_responses(self) -> list[ChatResponse]:
        """Hand over and clear the responses received since the last call (the runner's meter)."""
        drained, self.responses = self.responses, []
        return drained

    # -- prompt -------------------------------------------------------------------------------

    def _effective_stage(self, request: AgentRequest) -> str:
        """The stage the reply belongs to: an executed write with its read-back is an act reply.

        An explicit action request is planned from the explain step (the Gate promotes the turn
        afterwards), so the request can still say ``explain`` when the text to write is the
        confirmation of the action.
        """
        present = {result.tool for result in request.tool_results}
        if present & _WRITE_TOOLS and "get_payment_status" in present:
            return HubStage.ACT.value
        return request.stage

    def _model_writes(self, request: AgentRequest, stage: str) -> bool:
        """True once the stage's verified payload is in the session's tool results."""
        tools = _STAGE_TOOLS.get(stage)
        if tools is None:
            return False
        present = {result.tool for result in request.tool_results}
        if stage == HubStage.ACT.value:
            return bool(present & _WRITE_TOOLS) and "get_payment_status" in present
        return bool(present & set(tools))

    def _chat_request(self, request: AgentRequest, stage: str) -> ChatRequest:
        language = request.evidence.customer_language if request.evidence is not None else "es"
        return ChatRequest(
            role=Role.AGENT,
            messages=(
                Message(role=MessageRole.SYSTEM, content=self._prompts.system(stage, language)),
                Message(role=MessageRole.USER, content=self._user_message(request, stage)),
            ),
            purpose=f"agent-{stage}",
            temperature=0.0,
            max_tokens=COMPLETION_BUDGET,
            seed=self._seed,
            reasoning_effort=ReasoningEffort.LOW,
        )

    def _user_message(self, request: AgentRequest, stage: str) -> str:
        """The customer's redacted message, the playbook guidance and the record, then the retry.

        The message is the digest the verifier already builds (``redact_question``): NFR-1 keeps
        raw customer text, amounts and merchants out of an external model's context, and the
        record carries the amounts and merchants as structured, verified facts instead.
        """
        question = request.evidence.customer_question if request.evidence is not None else None
        sections = [f"CUSTOMER MESSAGE (redacted):\n{question or '(not available)'}"]
        if request.guidance is not None:
            sections.append(
                "GUIDANCE:\n"
                f"explain: {request.guidance.explain.strip()}\n"
                f"actions the playbook offers: {', '.join(request.guidance.actions) or 'none'}\n"
                f"escalate when: {request.guidance.escalate_when.strip()}"
            )
        sections.append(
            "RECORD:\n"
            + json.dumps(self._record(request, stage), indent=2, sort_keys=True, default=str)
        )
        if request.feedback:
            sections.append(
                self._prompts.retry_note(
                    [f"{verdict.criterion_id} ({verdict.reason})" for verdict in request.feedback]
                )
            )
        return "\n\n".join(sections)

    def _record(self, request: AgentRequest, stage: str) -> list[dict[str, Any]]:
        tools = _STAGE_TOOLS[stage]
        return [
            {"tool": result.tool, "result": result.payload}
            for result in request.tool_results
            if result.tool in tools
        ]

    # -- guards -------------------------------------------------------------------------------

    def _guard(self, response: ChatResponse) -> str:
        text = response.text.strip()
        if not text:
            raise AgentOutputError("the model returned an empty reply")
        if response.finish_reason == "length":
            raise AgentOutputError("the model's reply was cut off by the token budget")
        if len(text) > MAX_REPLY_CHARS:
            raise AgentOutputError(
                f"the model's reply is {len(text)} characters (cap {MAX_REPLY_CHARS})"
            )
        if _NOT_PROSE.search(text):
            raise AgentOutputError("the model answered in a tool-call or code dialect, not prose")
        return text
