"""The hub graph (TSD-009): one LangGraph graph for the stuck-payments workflow.

``build_hub_graph(deps)`` wires the merged parts into the stages of DESIGN 6.1:
``intake`` (session, Facts) -> ``classify`` (Laya scores -> ``decide_route``,
logged) -> one branch per route: the ``explain`` loop (agent draft -> the
stage's tools -> re-draft -> ``verify`` through the TSD-004 cascade),
``clarify`` (one question plus the problem-payment picker card),
``out_of_scope`` (an honest reply and a path to a person, no tools) and
``escalate`` (a case reference and a human; the full case file,
``open_investigation`` and ``interrupt()`` land with the investigate step).
A write the agent asks for goes through the ``act`` stage and its Gate:
``decide_gate`` rules on the exact action, ``allow`` issues a single-use
confirmation token and runs the write with a verified read-back, ``ask``
pauses on ``interrupt()`` for an operator's approval, and ``block`` refuses
naming the rule. The ``human`` route runs ``investigate`` (the complete
case file, a bank case through ``open_investigation`` when a payment is
focused) and ``handoff`` (the ``interrupt()`` for the operator queue);
``follow_up`` is the explain loop under its own stage on a resumed thread
with an open case.

Two design rules shape the module: the session token never passes through a
model (it travels in the invoke ``config``, never in ``HubState`` or an
``AgentRequest``; nodes resolve it to a ``Session`` through the issuer), and
every decision is logged (route, tool refusals, verification attempts, the
human hand-off) with ``session_ref``, never the token.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Literal, Protocol

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

from calvino.api.decide import scores_from_answers
from calvino.api.loader import SystemOneLoader
from calvino.classifiers import workflow_questions
from calvino.decision_log import DecisionLog
from calvino.hub.agent import AgentRequest, SupportAgent
from calvino.hub.playbook import Playbook, StatusGuidance, load_playbook
from calvino.hub.sessions import TrustedSessionIssuer
from calvino.hub.state import HubStage, HubState
from calvino.policy import ActionName, Facts, GateAction, Policy, decide_gate, decide_route
from calvino.records import DecisionRecord, GateVerdict, HumanAction, Route, Stage
from calvino.tools import TOOL_NAMES, BankTools, Session, ToolRefusal
from calvino.verifier import (
    Evidence,
    Judge,
    LayaChecker,
    Rubric,
    ToolResult,
    Verifier,
    evidence_from_tool_results,
)

# The agent may gather facts, but a runaway loop must not spin forever: after
# this many tool rounds the harness escalates instead of drafting again.
MAX_TOOL_ROUNDS = 8

READ_TOOLS = frozenset(
    {
        "get_customer_summary",
        "list_accounts",
        "get_account_entries",
        "get_entry_detail",
        "get_payment_status",
        "list_problem_transactions",
        "get_investigation_status",
    }
)

# Tools per stage (decision 24): reads in explain, clarify and follow-up; the
# writes only in act; open_investigation only in investigate. The Gate still
# checks every write (defense in depth).
STAGE_TOOLS: dict[HubStage, frozenset[str]] = {
    HubStage.EXPLAIN: READ_TOOLS,
    HubStage.CLARIFY: READ_TOOLS,
    HubStage.FOLLOW_UP: READ_TOOLS,
    HubStage.ACT: READ_TOOLS | {"request_cancellation", "retry_payment"},
    HubStage.INVESTIGATE: READ_TOOLS | {"open_investigation"},
    HubStage.OUT_OF_SCOPE: frozenset(),
}

# The consequential writes the act stage handles. ``open_investigation`` is
# the investigate step's write and lands with that commit.
WRITE_TOOLS = frozenset({"request_cancellation", "retry_payment"})

# The read-back ids the verifier's claimed-actions criterion knows (TSD-004):
# a reply may claim an action only under the id its read-back confirms.
READ_BACK_IDS = {"request_cancellation": "cancel_transfer", "retry_payment": "retry_payment"}

_ROUTE_STAGES: dict[Route, HubStage] = {
    Route.AGENTS: HubStage.EXPLAIN,
    Route.CLARIFY: HubStage.CLARIFY,
    Route.HUMAN: HubStage.INVESTIGATE,
    Route.OUT_OF_SCOPE: HubStage.OUT_OF_SCOPE,
}

# The deterministic hard-rule input for "explicitly asks for a human" (design
# rule: hard rules run before Laya and always win). A literal phrase scan on
# purpose: no model decides this, and Laya's needs_human score is the softer
# signal behind it. Spanish and English, the demo's two chat languages.
HUMAN_REQUEST_PHRASES: tuple[str, ...] = (
    "hablar con una persona",
    "hablar con alguien",
    "una persona real",
    "agente humano",
    "representante",
    "human agent",
    "real person",
    "talk to a person",
    "talk to a human",
    "speak to a person",
    "speak to a human",
)

# Fixed harness-authored replies. They are not model output, so they do not go
# through the verifier cascade; the cascade checks what the agent drafts.
CLARIFY_QUESTION = (
    "¿Sobre cuál de tus pagos quieres consultar? Dime el monto, la fecha o el "
    "destinatario y lo reviso."
)
OUT_OF_SCOPE_REPLY = (
    "Esto queda fuera de lo que puedo resolver aquí. Si quieres, te paso con "
    "una persona del equipo."
)
ESCALATE_REPLY = (
    "Una persona del equipo revisará tu caso y te responderá. Número de caso: {case_ref}."
)
REFUSAL_REPLY = (
    "No puedo hacer esa operación: la regla {rule} la detuvo. Si quieres, te paso con una persona."
)


class FraudContext(Protocol):
    """The harness-side risk signal behind the HR-FRAUD hard rule.

    Fraud flags are internal bank facts (``fraud_flagged`` never leaves the
    adapter), so the hub reads them through this seam: the demo wires the
    fixture's flags, production the real risk system. Never a model.
    """

    def is_flagged(self, session: Session) -> bool:
        """True when this customer's activity carries a fraud signal."""
        ...


class ConfirmationIssuer(Protocol):
    """Hub-side issuance of the single-use confirmation tokens (TSD-002).

    ``HmacConfirmationVerifier`` implements this for production and the
    tools' ``FakeConfirmationVerifier`` for tests. A token is bound to one
    customer, one action, one target payment, one amount and currency, so
    an issued token is never a pass for a different write.
    """

    def issue(
        self,
        *,
        customer_id: str,
        action: str,
        target_reference: str,
        amount: Decimal,
        currency: str,
    ) -> str:
        """Sign a token for exactly this action."""
        ...


@dataclass(frozen=True)
class HubDependencies:
    """Everything the graph nodes need, injected once at build time."""

    loader: SystemOneLoader
    policy: Policy
    tools: BankTools
    issuer: TrustedSessionIssuer
    agent: SupportAgent
    log: DecisionLog
    playbook: Playbook = field(default_factory=load_playbook)
    rubric: Rubric | None = None
    laya_checker: LayaChecker | None = None
    judge: Judge | None = None
    fraud_context: FraudContext | None = None
    # Hub-side confirmation-token issuance for the act stage; None fails
    # closed (a write without its token path never runs).
    confirmations: ConfirmationIssuer | None = None
    # The demo dataset is Spanish-first; the evidence language check reads this.
    customer_language: Literal["es", "pt"] = "es"


def _session_token(config: RunnableConfig | None) -> str | None:
    configurable = (config or {}).get("configurable") or {}
    token = configurable.get("session_token")
    return token if isinstance(token, str) else None


def _payload(result: Any) -> dict[str, Any]:
    """Serialize one tool result: contract models dump, lists become entries."""
    if isinstance(result, list):
        return {"entries": [item.model_dump(mode="json") for item in result]}
    return result.model_dump(mode="json")


def _focus(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    """The transaction a payload focuses on: its reference and status, if any."""
    entries = payload.get("entries")
    if isinstance(entries, list) and len(entries) == 1 and isinstance(entries[0], dict):
        payload = entries[0]
    reference = payload.get("entry_reference") or payload.get("original_reference")
    status = payload.get("status")
    return (
        reference if isinstance(reference, str) else None,
        status if isinstance(status, str) else None,
    )


def verified_card(state: HubState) -> dict[str, Any] | None:
    """The FR-7 card for a verified read turn, filled only from tool payloads.

    ``payment_status`` comes from the focused entry detail, ``case_status``
    from the investigation status on a follow-up. The act stage emits its
    own ``action_result`` card in the node, so it is skipped here. A turn
    without the matching verified result gets no card: a card is never
    filled from the draft's words.
    """
    stage = state.get("stage", HubStage.EXPLAIN)
    if stage == HubStage.ACT:
        return None
    results = list(state.get("tool_results") or [])
    if stage == HubStage.FOLLOW_UP:
        result = next((r for r in reversed(results) if r.tool == "get_investigation_status"), None)
        if result is None or not isinstance(result.payload.get("status"), str):
            return None
        payload: dict[str, Any] = {
            "case_ref": result.payload.get("case_id") or state.get("case_ref") or "",
            "status": result.payload["status"],
        }
        if result.payload.get("next_step"):
            payload["next_step"] = result.payload["next_step"]
        return {"key": "case_status", "payload": payload}
    result = next((r for r in reversed(results) if r.tool == "get_entry_detail"), None)
    if result is None or not isinstance(result.payload.get("entry_reference"), str):
        return None
    detail = result.payload
    payload = {
        "entry_reference": detail["entry_reference"],
        "amount": detail.get("amount"),
        "currency": detail.get("currency"),
        "status": detail.get("status"),
        "booking_date": detail.get("booking_date"),
    }
    if detail.get("remittance_information"):
        payload["remittance_information"] = detail["remittance_information"]
    return {"key": "payment_status", "payload": payload}


def case_file_of(state: HubState) -> list[dict[str, str]]:
    """The complete case file for a human (AC-4): request, verified facts,
    the action with its gate verdict, and why the turn reached a person.

    Summaries only, never raw payloads: the file travels in the operator
    interrupt and into the log, and both stay small and free of data the
    turn never verified.
    """
    entries: list[dict[str, str]] = [{"request": state.get("message", "")}]
    for result in state.get("tool_results", []):
        reference, status = _focus(result.payload)
        summary = result.tool
        if reference:
            summary += f" {reference}"
        if status:
            summary += f" -> {status}"
        entries.append({"verified_fact": summary})
    action = state.get("action")
    if action:
        entries.append({"action": f"{action} ({state.get('gate_verdict') or 'no verdict'})"})
    reason = state.get("escalate_reason") or state.get("rule_id")
    if reason:
        entries.append({"open_question": f"routed to a human by {reason}"})
    return entries


def build_hub_graph(
    deps: HubDependencies, checkpointer: BaseCheckpointSaver | None = None
) -> CompiledStateGraph:
    """Compile the hub graph over one set of dependencies.

    The service compiles with a checkpointer for the interrupt-based human
    steps (the act stage's approval needs one); tests compile without one
    and invoke with a ``session_token`` in the config's ``configurable``.
    """

    def log_decision(
        state: HubState,
        *,
        stage: Stage,
        rule_id: str,
        verdict: str,
        inputs_summary: dict[str, str | int | float | bool | None] | None = None,
    ) -> None:
        deps.log.append(
            DecisionRecord(
                stage=stage,
                session_ref=state.get("session_ref", ""),
                inputs_summary=inputs_summary or {},
                rule_id=rule_id,
                policy_version=deps.policy.version,
                verdict=verdict,
                latency_ms=0.0,
            )
        )

    def resolve_session(config: RunnableConfig | None) -> Session | None:
        return deps.issuer.resolve(_session_token(config))

    def evidence_of(state: HubState) -> Evidence:
        return evidence_from_tool_results(
            state.get("tool_results", []),
            customer_language=deps.customer_language,
            read_backs=frozenset(state.get("read_backs", [])),
        )

    def guidance_of(state: HubState) -> StatusGuidance | None:
        status = state.get("status")
        if status is None or status not in deps.playbook.statuses:
            return None
        return deps.playbook.guidance(status)

    def refusal(
        state: HubState, updates: dict[str, Any], tool: str, rule_id: str
    ) -> dict[str, Any]:
        """End the turn with a refusal card naming the rule (AC-6).

        Refusals never reach the agent as raw text: the harness logs the
        attempt and replies with the fixed refusal message.
        """
        log_decision(
            state,
            stage=Stage.HARD_RULES,
            rule_id=rule_id,
            verdict="refuse",
            inputs_summary={"tool": tool},
        )
        updates["reply"] = REFUSAL_REPLY.format(rule=rule_id)
        updates["card"] = {"key": "refusal", "payload": {"rule": rule_id}}
        return updates

    def intake(state: HubState, config: RunnableConfig) -> dict[str, Any]:
        """Resolve the session and build the hard-rule ``Facts`` (never from a model)."""
        session = resolve_session(config)
        if session is None:
            log_decision(
                state,
                stage=Stage.HARD_RULES,
                rule_id="FC-SESSION",
                verdict=Route.HUMAN.value,
                inputs_summary={"reason": "no live session for this request"},
            )
            return {
                "route": Route.HUMAN,
                "rule_id": "FC-SESSION",
                "escalate_reason": "FC-SESSION",
            }
        lowered = state.get("message", "").casefold()
        asks_for_human = any(phrase in lowered for phrase in HUMAN_REQUEST_PHRASES)
        fraud_signal = (
            deps.fraud_context.is_flagged(session) if deps.fraud_context is not None else False
        )
        return {
            "facts": Facts(
                session_ref=state.get("session_ref", ""),
                fraud_signal=fraud_signal,
                asks_for_human=asks_for_human,
                # The demo has no real auth, regulator or vulnerability
                # signals; the fields stay inert until a bank core feeds them.
                auth_failures=0,
                via_regulator=False,
                vulnerable_customer=False,
            ),
            "stage": HubStage.EXPLAIN,
            "tool_rounds": 0,
            # Per-turn resets: on a resumed thread a stale failure, action or
            # reply must not leak into the new turn. The focused transaction,
            # an open case and the accumulated evidence are thread state and
            # stay on purpose.
            "escalated": False,
            "escalate_reason": None,
            "action": None,
            "gate_verdict": None,
            "action_amount": None,
            "action_currency": None,
            "draft": None,
            "question": None,
            "reply": None,
            "card": None,
            "pending_calls": [],
            "case_file": [],
        }

    def classify(state: HubState, config: RunnableConfig) -> dict[str, Any]:
        """Laya answers -> calibrated scores -> ``decide_route``; the record is logged."""
        try:
            answers = {
                answer.question_id: answer
                for answer in deps.loader.classify(state.get("message", ""), workflow_questions())
            }
            scores = scores_from_answers(answers)
        except Exception:
            # A failing System 1 leaves nothing to decide on: fail closed to a
            # person, exactly like missing scores inside decide_route.
            log_decision(
                state,
                stage=Stage.CLASSIFIER,
                rule_id="FC-CLASSIFY",
                verdict=Route.HUMAN.value,
                inputs_summary={"reason": "classifier error"},
            )
            return {
                "route": Route.HUMAN,
                "rule_id": "FC-CLASSIFY",
                "escalate_reason": "FC-CLASSIFY",
            }
        facts = state.get("facts")
        decision = decide_route(scores, facts.model_dump() if facts else {}, deps.policy)
        deps.log.append(decision.record)
        stage = _ROUTE_STAGES[decision.route]
        if decision.route is Route.AGENTS and state.get("case_ref"):
            # A resumed thread with an open case: the agent follows up on it
            # (get_investigation_status is a follow-up read, decision 24).
            stage = HubStage.FOLLOW_UP
        return {
            "scores": scores,
            "route": decision.route,
            "rule_id": decision.rule_id,
            "human_action": decision.human_action,
            "stage": stage,
        }

    def explain(state: HubState, config: RunnableConfig) -> dict[str, Any]:
        """One agent step: a draft reply, or the tool calls it needs first."""
        if state.get("tool_rounds", 0) >= MAX_TOOL_ROUNDS:
            return {"escalate_reason": "TOOL-LOOP"}
        request = AgentRequest(
            stage=str(state.get("stage", HubStage.EXPLAIN)),
            message=state.get("message", ""),
            evidence=evidence_of(state),
            guidance=guidance_of(state),
            case_ref=state.get("case_ref"),
        )
        try:
            draft = deps.agent.draft(request)
        except Exception:
            # An agent that errors leaves nothing to verify: fail closed.
            return {"escalate_reason": "AGENT-ERROR"}
        if draft.tool_calls:
            return {
                "pending_calls": [call.model_dump() for call in draft.tool_calls],
                "draft": None,
            }
        return {"draft": draft.text, "pending_calls": []}

    def run_tools(state: HubState, config: RunnableConfig) -> dict[str, Any]:
        """Run the agent's requested calls: stage-scoped, session attached out of band."""
        session = resolve_session(config)
        allowed = STAGE_TOOLS.get(state.get("stage", HubStage.EXPLAIN), frozenset())
        updates: dict[str, Any] = {
            "pending_calls": [],
            "tool_rounds": state.get("tool_rounds", 0) + 1,
        }
        results: list[ToolResult] = []
        for call in state.get("pending_calls", []):
            name = str(call.get("tool", ""))
            arguments = call.get("arguments") or {}
            if name not in allowed or name not in TOOL_NAMES:
                return refusal(state, updates, name, "TOOL-NOT-ALLOWED")
            try:
                result = getattr(deps.tools, name)(session, **arguments)
            except ToolRefusal as tool_refusal:
                return refusal(state, updates, name, tool_refusal.rule.value)
            except TypeError:
                # Arguments that do not match the tool's signature are the
                # agent's mistake, refused like any other bad call.
                return refusal(state, updates, name, "TOOL-BAD-ARGUMENTS")
            payload = _payload(result)
            results.append(ToolResult(tool=name, payload=payload))
            reference, status = _focus(payload)
            if reference is not None:
                updates["entry_reference"] = reference
            if status is not None:
                updates["status"] = status
        updates["tool_results"] = results
        return updates

    def gate(state: HubState, config: RunnableConfig) -> dict[str, Any]:
        """The Gate rules on the exact action the agent asked for, never on its words.

        The target's amount, currency and status are read from the bank, not
        taken from the agent's arguments: a model never supplies the facts a
        verdict rests on. ``allow`` proceeds to the write, ``ask`` pauses for
        an operator, ``block`` refuses naming the rule; the record is logged.
        """
        updates: dict[str, Any] = {"pending_calls": [], "stage": HubStage.ACT}
        session = resolve_session(config)
        if session is None:
            return {**updates, "escalate_reason": "FC-SESSION"}
        call = next(
            (c for c in state.get("pending_calls", []) if str(c.get("tool", "")) in WRITE_TOOLS),
            None,
        )
        if call is None:  # after_explain only routes here with a write pending
            return {**updates, "escalate_reason": "FC-ACT-INPUTS"}
        name = str(call.get("tool", ""))
        entry_reference = (call.get("arguments") or {}).get("entry_reference")
        if not isinstance(entry_reference, str) or not entry_reference:
            return refusal(state, updates, name, "TOOL-BAD-ARGUMENTS")
        try:
            detail = deps.tools.get_entry_detail(session, entry_reference)
        except ToolRefusal as tool_refusal:
            return refusal(state, updates, name, tool_refusal.rule.value)
        action = GateAction(
            name=ActionName(name),
            transaction_status=detail.status.value,
            amount=float(detail.amount),
            currency=detail.currency,
            # get_entry_detail succeeded under this session, so the tool has
            # already verified ownership of the target.
            owner_verified=True,
        )
        facts = state.get("facts")
        decision = decide_gate(
            action, state.get("scores") or {}, facts.model_dump() if facts else {}, deps.policy
        )
        deps.log.append(decision.record)
        payload = _payload(detail)
        _, status = _focus(payload)
        updates.update(
            {
                "action": name,
                "entry_reference": entry_reference,
                "rule_id": decision.rule_id,
                "human_action": decision.human_action,
                "gate_verdict": decision.verdict.value,
                "action_amount": str(detail.amount),
                "action_currency": detail.currency,
                "tool_results": [ToolResult(tool="get_entry_detail", payload=payload)],
            }
        )
        if status is not None:
            updates["status"] = status
        if decision.verdict is GateVerdict.BLOCK:
            # The gate record above is the log entry; the reply names the rule.
            updates["reply"] = REFUSAL_REPLY.format(rule=decision.rule_id)
            updates["card"] = {"key": "refusal", "payload": {"rule": decision.rule_id}}
        return updates

    def act(state: HubState, config: RunnableConfig) -> dict[str, Any]:
        """Run the allowed write: confirmation token, execution, verified read-back.

        On an ``ask`` verdict the node pauses on ``interrupt()`` and resumes
        when an operator approves or denies (the service compiles with a
        checkpointer for this). Nothing before the interrupt has side
        effects, so the node's replay on resume is safe. The token is issued
        for exactly this action and the tool consumes it; the idempotency key
        is derived from the session, never model-supplied.
        """
        updates: dict[str, Any] = {}
        name = state.get("action") or ""
        entry_reference = state.get("entry_reference") or ""
        session = resolve_session(config)
        if session is None or name not in WRITE_TOOLS or not entry_reference:
            return {"escalate_reason": "FC-ACT-INPUTS"}
        if state.get("gate_verdict") == GateVerdict.ASK.value:
            approved = interrupt(
                {
                    "type": "approve_action",
                    "action": name,
                    "entry_reference": entry_reference,
                    "amount": state.get("action_amount"),
                    "currency": state.get("action_currency"),
                    "rule_id": state.get("rule_id"),
                    "session_ref": state.get("session_ref", ""),
                }
            )
            if not approved:
                return {
                    "escalate_reason": "APPROVAL-DENIED",
                    "human_action": HumanAction.APPROVE_ACTION,
                }
        if deps.confirmations is None:
            # No issuer, no write: a consequential action without its token
            # path fails closed instead of running unconfirmed.
            return {"escalate_reason": "FC-CONFIRMATIONS"}
        try:
            amount = Decimal(str(state.get("action_amount")))
            currency = str(state.get("action_currency"))
        except InvalidOperation:
            return {"escalate_reason": "FC-CONFIRMATIONS"}
        token = deps.confirmations.issue(
            customer_id=session.customer_id,
            action=name,
            target_reference=entry_reference,
            amount=amount,
            currency=currency,
        )
        idempotency_key = f"{state.get('session_ref') or 'session'}-{name}-{entry_reference}"
        try:
            result = getattr(deps.tools, name)(session, entry_reference, idempotency_key, token)
            read_back = deps.tools.get_payment_status(session, entry_reference)
        except ToolRefusal as tool_refusal:
            # The tool's own checks (fraud flag, eligibility, token) refused:
            # defense in depth, named and logged like any other refusal.
            return refusal(state, updates, name, tool_refusal.rule.value)
        updates["tool_results"] = [
            ToolResult(tool=name, payload=_payload(result)),
            ToolResult(tool="get_payment_status", payload=_payload(read_back)),
        ]
        updates["read_backs"] = [READ_BACK_IDS[name]]
        _, status = _focus(_payload(read_back))
        if status is not None:
            updates["status"] = status
        # FR-7: the action result card, filled from the verified read-back.
        result_payload: dict[str, Any] = {"action": name, "entry_reference": entry_reference}
        if status is not None:
            result_payload["status"] = status
        updates["card"] = {"key": "action_result", "payload": result_payload}
        return updates

    def investigate(state: HubState, config: RunnableConfig) -> dict[str, Any]:
        """The human step: the complete case file (AC-4) and a bank case.

        ``open_investigation`` runs only when a payment is focused (a resumed
        thread that already found one) and through the gate, which confirms
        every write: BLOCK stops the call, and ASK folds into the operator
        handoff below — interrupting for it twice would queue the same case
        for the same human twice. When no bank case can open, the turn still
        reaches an operator with the file: a human route never fails closed
        against a human.
        """
        case_file = list(state.get("case_file") or []) or case_file_of(state)
        updates: dict[str, Any] = {
            "stage": HubStage.INVESTIGATE,
            "case_file": case_file,
        }
        session = resolve_session(config)
        entry_reference = state.get("entry_reference")
        case_ref = state.get("case_ref")
        if session is not None and entry_reference and case_ref is None:
            detail = None
            try:
                detail = deps.tools.get_entry_detail(session, entry_reference)
            except ToolRefusal as tool_refusal:
                log_decision(
                    state,
                    stage=Stage.HARD_RULES,
                    rule_id=tool_refusal.rule.value,
                    verdict="refuse",
                    inputs_summary={"write": ActionName.OPEN_INVESTIGATION.value},
                )
            token: str | None = None
            if detail is not None:
                facts = state.get("facts")
                gate_action = GateAction(
                    name=ActionName.OPEN_INVESTIGATION,
                    transaction_status=detail.status.value,
                    amount=float(detail.amount),
                    currency=detail.currency,
                    # get_entry_detail succeeded under this session: the tool
                    # has already verified ownership of the target.
                    owner_verified=True,
                )
                decision = decide_gate(
                    gate_action,
                    state.get("scores") or {},
                    facts.model_dump() if facts else {},
                    deps.policy,
                )
                deps.log.append(decision.record)
                updates.update(
                    {
                        "gate_verdict": decision.verdict.value,
                        "action": ActionName.OPEN_INVESTIGATION.value,
                        "action_amount": str(detail.amount),
                        "action_currency": detail.currency,
                    }
                )
                if deps.confirmations is not None and decision.verdict is not GateVerdict.BLOCK:
                    token = deps.confirmations.issue(
                        customer_id=session.customer_id,
                        action=ActionName.OPEN_INVESTIGATION.value,
                        target_reference=entry_reference,
                        amount=detail.amount,
                        currency=detail.currency,
                    )
            if token is not None:
                idempotency_key = (
                    f"{state.get('session_ref') or 'session'}"
                    f"-{ActionName.OPEN_INVESTIGATION.value}-{entry_reference}"
                )
                try:
                    investigation = deps.tools.open_investigation(
                        session,
                        entry_reference,
                        f"Routed to a human by {state.get('rule_id') or 'policy'}",
                        idempotency_key,
                        token,
                    )
                except ToolRefusal as tool_refusal:
                    # Defense in depth refused after the gate confirmed: the
                    # refusal is named and logged, and the operator queue
                    # still gets the file below.
                    log_decision(
                        state,
                        stage=Stage.HARD_RULES,
                        rule_id=tool_refusal.rule.value,
                        verdict="refuse",
                        inputs_summary={"write": ActionName.OPEN_INVESTIGATION.value},
                    )
                    investigation = None
                if investigation is not None:
                    case_ref = investigation.case_id
                    updates["tool_results"] = [
                        ToolResult(tool="open_investigation", payload=_payload(investigation)),
                    ]
        if case_ref is None:
            case_ref = f"case-{uuid.uuid4().hex[:12]}"
        updates["case_ref"] = case_ref
        return updates

    def handoff(state: HubState, config: RunnableConfig) -> dict[str, Any]:
        """The operator queue: ``interrupt()`` parks the turn until an
        operator resumes it with their decision (HubService.resume).

        Kept separate from investigate so nothing with a side effect re-runs
        on resume: the case file and the bank case are written before this
        node, and interrupt() is its first statement.
        """
        case_ref = str(state.get("case_ref") or "")
        reason = state.get("escalate_reason") or state.get("rule_id") or "route-human"
        decision = interrupt(
            {
                "type": "operator_queue",
                "case_ref": case_ref,
                "session_ref": state.get("session_ref", ""),
                "reason": reason,
                "case_file": list(state.get("case_file") or []),
            }
        )
        log_decision(
            state,
            stage=Stage.HUMAN,
            rule_id=str(state.get("rule_id") or reason),
            verdict=(state.get("human_action") or HumanAction.FULL_TRANSFER).value,
            inputs_summary={
                "reason": reason,
                "case_ref": case_ref,
                "operator_decision": str(decision),
            },
        )
        return {
            "escalated": True,
            "reply": ESCALATE_REPLY.format(case_ref=case_ref),
            "card": {"key": "case_opened", "payload": {"case_ref": case_ref}},
        }

    def verify(state: HubState, config: RunnableConfig) -> dict[str, Any]:
        """The TSD-004 cascade over the draft: pass replies, escalate failures."""
        draft = state.get("draft") or ""
        evidence = evidence_of(state)
        verifier = Verifier(
            deps.rubric, deps.laya_checker, deps.judge, deps.log, state.get("session_ref")
        )
        retried: list[str] = []

        def regenerate(failed: list) -> str:
            request = AgentRequest(
                stage=str(state.get("stage", HubStage.EXPLAIN)),
                message=state.get("message", ""),
                evidence=evidence,
                guidance=guidance_of(state),
                feedback=tuple(failed),
                case_ref=state.get("case_ref"),
            )
            redraft = deps.agent.draft(request)
            if redraft.text is None:
                raise ValueError("the agent asked for tools on a verification retry")
            retried.append(redraft.text)
            return redraft.text

        outcome = verifier.run(draft, evidence, regenerate)
        if outcome.escalated:
            return {
                "escalate_reason": "VERIFY-FAILED",
                "case_file": outcome.case_file_entries(),
                "escalated": True,
            }
        passed: dict[str, Any] = {"reply": retried[-1] if retried else draft, "escalated": False}
        card = verified_card(state)
        if card is not None:
            passed["card"] = card
        return passed

    def clarify(state: HubState, config: RunnableConfig) -> dict[str, Any]:
        """One question, plus the picker card when the customer has problem payments."""
        session = resolve_session(config)
        updates: dict[str, Any] = {
            "question": CLARIFY_QUESTION,
            "reply": CLARIFY_QUESTION,
            "card": None,
        }
        if session is None:
            return updates
        try:
            problems = deps.tools.list_problem_transactions(session)
        except ToolRefusal:
            return updates
        entries = [entry.model_dump(mode="json") for entry in problems]
        updates["tool_results"] = [
            ToolResult(tool="list_problem_transactions", payload={"entries": entries})
        ]
        if entries:
            updates["card"] = {"key": "problem_transactions", "payload": {"entries": entries}}
        return updates

    def out_of_scope(state: HubState, config: RunnableConfig) -> dict[str, Any]:
        """An honest reply and a path to a person; no agent loop, no tools."""
        return {
            "reply": OUT_OF_SCOPE_REPLY,
            "card": {"key": "human_path", "payload": {}},
        }

    def escalate(state: HubState, config: RunnableConfig) -> dict[str, Any]:
        """The failure sink: a case reference, the case file so far, a logged record.

        The deliberate human route runs investigate and handoff instead; this
        sink carries the failure paths (session, classifier, tool loop, agent
        error, verification, denied approval) and reuses an open case when
        the thread already has one.
        """
        case_ref = state.get("case_ref") or f"case-{uuid.uuid4().hex[:12]}"
        reason = state.get("escalate_reason") or state.get("rule_id") or "route-human"
        case_file = list(state.get("case_file", []))
        if not case_file:
            case_file = [{"request": state.get("message", "")}]
        log_decision(
            state,
            stage=Stage.HUMAN,
            rule_id=state.get("rule_id") or reason,
            verdict=(state.get("human_action") or HumanAction.FULL_TRANSFER).value,
            inputs_summary={"reason": reason, "case_ref": case_ref},
        )
        return {
            "case_ref": case_ref,
            "case_file": case_file,
            "escalated": True,
            "reply": ESCALATE_REPLY.format(case_ref=case_ref),
            "card": {"key": "case_opened", "payload": {"case_ref": case_ref}},
        }

    def after_intake(state: HubState) -> str:
        return "escalate" if state.get("escalate_reason") else "classify"

    def after_classify(state: HubState) -> str:
        if state.get("escalate_reason"):
            # FC-CLASSIFY: the classifier failed, which goes to the failure
            # sink rather than to the investigate queue.
            return "escalate"
        route = state.get("route")
        if route is Route.AGENTS:
            return "explain"
        if route is Route.CLARIFY:
            return "clarify"
        if route is Route.OUT_OF_SCOPE:
            return "out_of_scope"
        return "investigate"

    def after_explain(state: HubState) -> str:
        if state.get("escalate_reason"):
            return "escalate"
        calls = state.get("pending_calls") or []
        # A requested write goes through the Gate, never around it; the
        # harness rules on one consequential action per turn, so the first
        # write in the draft wins and the agent re-asks any reads afterwards.
        if any(str(call.get("tool", "")) in WRITE_TOOLS for call in calls):
            return "gate"
        if calls:
            return "run_tools"
        return "verify"

    def after_gate(state: HubState) -> str:
        if state.get("reply"):  # block: the refusal ends the turn
            return END
        if state.get("escalate_reason"):
            return "escalate"
        return "act"

    def after_act(state: HubState) -> str:
        if state.get("reply"):  # a tool-side refusal ends the turn
            return END
        if state.get("escalate_reason"):
            return "escalate"
        # The write ran and was read back: the agent explains the outcome.
        return "explain"

    def after_tools(state: HubState) -> str:
        # A refusal ends the turn with its card; otherwise the agent re-drafts.
        return END if state.get("reply") else "explain"

    def after_verify(state: HubState) -> str:
        return "escalate" if state.get("escalated") else END

    builder = StateGraph(HubState)
    builder.add_node("intake", intake)
    builder.add_node("classify", classify)
    builder.add_node("explain", explain)
    builder.add_node("run_tools", run_tools)
    builder.add_node("gate", gate)
    builder.add_node("act", act)
    builder.add_node("investigate", investigate)
    builder.add_node("handoff", handoff)
    builder.add_node("verify", verify)
    builder.add_node("clarify", clarify)
    builder.add_node("out_of_scope", out_of_scope)
    builder.add_node("escalate", escalate)
    builder.add_edge(START, "intake")
    builder.add_conditional_edges(
        "intake", after_intake, {"classify": "classify", "escalate": "escalate"}
    )
    builder.add_conditional_edges(
        "classify",
        after_classify,
        {
            "explain": "explain",
            "clarify": "clarify",
            "out_of_scope": "out_of_scope",
            "investigate": "investigate",
            "escalate": "escalate",
        },
    )
    builder.add_conditional_edges(
        "explain",
        after_explain,
        {"run_tools": "run_tools", "gate": "gate", "verify": "verify", "escalate": "escalate"},
    )
    builder.add_conditional_edges("run_tools", after_tools, {"explain": "explain", END: END})
    builder.add_conditional_edges(
        "gate", after_gate, {"act": "act", "escalate": "escalate", END: END}
    )
    builder.add_conditional_edges(
        "act", after_act, {"explain": "explain", "escalate": "escalate", END: END}
    )
    builder.add_conditional_edges("verify", after_verify, {"escalate": "escalate", END: END})
    builder.add_edge("clarify", END)
    builder.add_edge("out_of_scope", END)
    builder.add_edge("investigate", "handoff")
    builder.add_edge("handoff", END)
    builder.add_edge("escalate", END)
    return builder.compile(checkpointer=checkpointer)
