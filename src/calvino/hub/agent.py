"""The support agent interface (TSD-009, decision 20).

The language work sits behind ``SupportAgent`` so the hub never depends on a
provider: tests and the demo use ``ScriptedAgent``, and the Qwen model through
HF Inference Providers (T-301) plugs into the same protocol later. Two design
rules shape ``AgentRequest``: the session token never passes through a model
(it is not a field here, and the harness attaches it to tool calls out of
band), and the agent sees only verified facts (tool results), never raw
adapter data.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from calvino.hub.playbook import StatusGuidance
from calvino.verifier.evidence import Evidence
from calvino.verifier.verdicts import CriterionVerdict


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ToolCall(_Frozen):
    """A tool the agent asks the harness to call.

    Arguments are the tool's own parameters minus the session: the harness
    attaches the session out of band, so a model can never name a customer.
    """

    tool: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


class AgentRequest(_Frozen):
    """Everything the agent may see for one drafting step.

    ``feedback`` carries the verifier's failed criteria on the single retry
    (TSD-004 cascade); it is empty on the first draft. ``guidance`` is the
    playbook entry for the transaction status (decision 24), when known.
    """

    stage: str = Field(min_length=1)
    message: str
    evidence: Evidence | None = None
    guidance: StatusGuidance | None = None
    feedback: tuple[CriterionVerdict, ...] = ()


class AgentDraft(_Frozen):
    """One agent step: a reply, tool calls to make first, or both.

    A draft with neither text nor tool calls is rejected: the agent must
    either answer or ask for a fact, never return an empty step.
    """

    text: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()

    @model_validator(mode="after")
    def _has_a_step(self) -> AgentDraft:
        if self.text is None and not self.tool_calls:
            raise ValueError("a draft needs text, tool calls, or both")
        return self


class SupportAgent(Protocol):
    """The language work: draft one step from the verified context."""

    def draft(self, request: AgentRequest) -> AgentDraft:
        """Return the next step for this request."""
        ...


class ScriptedAgent:
    """A scripted agent for tests and the no-provider demo.

    Returns the queued drafts in order and records every request, so tests
    can assert what the model would have seen (including that no token ever
    appears in an ``AgentRequest``). An exhausted script raises: the hub
    treats an agent error as a fail-closed escalation, and a test that runs
    out of script should fail loudly rather than drift into a fallback.
    """

    def __init__(self, drafts: Sequence[AgentDraft]) -> None:
        self._drafts = list(drafts)
        self.requests: list[AgentRequest] = []

    def draft(self, request: AgentRequest) -> AgentDraft:
        self.requests.append(request)
        if not self._drafts:
            raise RuntimeError("the scripted agent has no draft left")
        return self._drafts.pop(0)
