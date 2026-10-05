"""The hub's service facade (TSD-009): one call per customer message.

``HubService.handle_message`` runs one turn on the persona's thread and
returns a ``HubReply``. When the turn parks on an ``interrupt()`` — the
operator queue (handoff) or an action approval (act) — the reply names what
it waits for, and ``HubService.resume`` continues the thread with the
operator's decision. Every reply carries the turn's decision trace (the
records the harness logged, in order) for the glass-box panel. The ref an
operator holds is the case ref for queued cases and the thread ref for
approvals; both map back to the thread here.
The checkpointer lives on ``CALVINO_DATA_DIR`` when set and falls back to
memory (tests and ephemeral runs). One thread per persona is enough for the
demo, and the pending-turn registry is process state, like the demo's
sessions.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict, Field

from calvino.hub.graph import HubDependencies, build_hub_graph
from calvino.records import DecisionRecord, Route, Stage, session_ref_for


class OperatorQueueItem(BaseModel):
    """One case in the operator queue (TSD-023)."""

    model_config = ConfigDict(frozen=True)

    case_ref: str
    persona: str
    status: Literal["pending_approval", "in_investigation", "refused", "resolved"]
    reason_rule_id: str
    created_at: str
    customer_message: str
    entry_reference: str | None = None
    amount: str | None = None
    currency: str | None = None
    target_action: Literal["cancel_payment", "retry_payment", "open_investigation"] | None = None
    awaiting_ref: str | None = None
    gate_verdict: str | None = None


DEFAULT_FALLBACK_CASES: tuple[OperatorQueueItem, ...] = (
    OperatorQueueItem(
        case_ref="CASE-ANA-001",
        persona="ana",
        status="in_investigation",
        reason_rule_id="RT-NEEDS-PERSON",
        created_at="2026-10-05T06:00:00Z",
        customer_message="Necesito hablar con un humano urgente, mi transferencia no llega.",
        entry_reference="TX-78219",
        amount="12500.00",
        currency="MXN",
        target_action="open_investigation",
        awaiting_ref="CASE-ANA-001",
        gate_verdict=None,
    ),
    OperatorQueueItem(
        case_ref="CASE-LUCIA-002",
        persona="lucia",
        status="pending_approval",
        reason_rule_id="GATE-AMOUNT-LIMIT",
        created_at="2026-10-05T06:15:00Z",
        customer_message="Por favor reintenten mi pago de alquiler que falló ayer.",
        entry_reference="TX-99412",
        amount="45000.00",
        currency="MXN",
        target_action="retry_payment",
        awaiting_ref="persona-lucia",
        gate_verdict="ask",
    ),
    OperatorQueueItem(
        case_ref="CASE-CARLOS-003",
        persona="carlos",
        status="refused",
        reason_rule_id="TOOL-NOT-OWNER",
        created_at="2026-10-05T06:20:00Z",
        customer_message="Quiero cancelar una transferencia que no es de mi cuenta.",
        entry_reference="TX-55120",
        amount="8500.00",
        currency="MXN",
        target_action="cancel_payment",
        awaiting_ref="CASE-CARLOS-003",
        gate_verdict="block",
    ),
)


class TraceStep(BaseModel):
    """One decision of the turn, as the glass box shows it (PRD FR-12).

    A read-only view of the ``DecisionRecord`` the harness logged: stage,
    rule, verdict, calibrated scores and the redacted inputs summary. The
    glass box reads only the trace, so the panel can never show data the
    harness did not log.
    """

    model_config = ConfigDict(frozen=True)

    stage: str
    rule_id: str | None
    verdict: str
    scores: dict[str, float] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)


class HubReply(BaseModel):
    """What the app shows for one turn (PRD FR-7).

    ``card`` is a key plus payload from the fixed catalog: the hub emits it,
    the app renders it. ``awaiting`` names the interrupt a parked turn waits
    for (``operator_queue`` or ``approve_action``) and ``awaiting_ref`` is
    the ref ``HubService.resume`` continues it with. ``trace`` holds the
    decision records this turn appended, in order (PRD FR-12).
    """

    model_config = ConfigDict(frozen=True)

    reply: str
    card: dict[str, Any] | None = None
    route: str | None = None
    case_ref: str | None = None
    escalated: bool = False
    awaiting: str | None = None
    awaiting_ref: str | None = None
    trace: tuple[TraceStep, ...] = ()


def _default_checkpointer() -> Any:
    """Sqlite under ``CALVINO_DATA_DIR`` when set; memory otherwise."""
    data_dir = os.environ.get("CALVINO_DATA_DIR")
    if not data_dir:
        return InMemorySaver()
    path = Path(data_dir) / "hub-checkpoints.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True)
    # The demo API serves requests from a thread pool; sqlite connections
    # are per-thread by default, so the shared checkpointer connection opts
    # out and serializes through LangGraph's own locking.
    saver = SqliteSaver(sqlite3.connect(path, check_same_thread=False))
    saver.setup()
    return saver


class HubService:
    """The demo's entry point to the hub graph: messages in, replies out."""

    def __init__(self, deps: HubDependencies, checkpointer: Any | None = None) -> None:
        self._deps = deps
        self._graph = build_hub_graph(deps, checkpointer=checkpointer or _default_checkpointer())
        # Ref -> thread and token: keyed by the thread ref, plus the case ref
        # a queued interrupt hands the operator.
        self._threads: dict[str, dict[str, str]] = {}
        self._cases: dict[str, OperatorQueueItem] = {}
        self._cases_by_ref: dict[str, OperatorQueueItem] = {}

    def list_cases(self) -> list[OperatorQueueItem]:
        """List all cases in the queue, returning seeded fallback cases when empty (TSD-023)."""
        if not self._cases:
            return list(DEFAULT_FALLBACK_CASES)
        return list(self._cases.values())

    def handle_message(self, persona: str, text: str) -> HubReply:
        """Run one customer turn on the persona's thread."""
        thread_id = f"persona-{persona}"
        token, session_ref = self._deps.issuer.issue(persona)
        self._threads[thread_id] = {"thread_id": thread_id, "token": token}
        seen = self._logged_count()
        state = self._graph.invoke(
            {"persona": persona, "session_ref": session_ref, "message": text},
            config={"configurable": {"thread_id": thread_id, "session_token": token}},
        )
        return self._reply_of(state, thread_id, self._turn_trace(seen))

    def resume(
        self,
        ref: str,
        operator_decision: Any,
        actor_id: str = "operator:demo-agent-01",
        justification: str | None = None,
    ) -> HubReply:
        """Continue a parked turn with the operator's decision.

        ``ref`` is what the interrupt handed the operator: the case ref for
        the operator queue, the thread ref for an action approval. An unknown
        ref raises instead of guessing a thread (fail closed).

        Core safety invariant (decision 37): A human operator cannot override a
        Gate block. If gate_verdict is 'block', an approval decision raises ValueError.
        """
        case = self._cases_by_ref.get(ref) or self._cases.get(ref)
        if case is None:
            for fb in DEFAULT_FALLBACK_CASES:
                if fb.awaiting_ref == ref or fb.case_ref == ref:
                    case = fb
                    break

        if case is not None and case.gate_verdict == "block" and operator_decision is True:
            raise ValueError(f"cannot approve action with Gate block: rule {case.reason_rule_id}")

        thread = self._threads.get(ref)
        if thread is None:
            if case is not None:
                new_status = "refused" if operator_decision is False else "resolved"
                updated_case = OperatorQueueItem(
                    case_ref=case.case_ref,
                    persona=case.persona,
                    status=new_status,
                    reason_rule_id=case.reason_rule_id,
                    created_at=case.created_at,
                    customer_message=case.customer_message,
                    entry_reference=case.entry_reference,
                    amount=case.amount,
                    currency=case.currency,
                    target_action=case.target_action,
                    awaiting_ref=case.awaiting_ref,
                    gate_verdict=case.gate_verdict,
                )
                self._cases[case.case_ref] = updated_case
                if case.awaiting_ref:
                    self._cases_by_ref[case.awaiting_ref] = updated_case

                self._deps.log.append(
                    DecisionRecord(
                        stage=Stage.HUMAN,
                        session_ref=session_ref_for(f"seed-session-{ref}"),
                        inputs_summary={
                            "actor_id": actor_id,
                            "case_ref": case.case_ref,
                            "decision": str(operator_decision),
                            "justification": justification or "Operator resolved case in console",
                        },
                        verdict="approved"
                        if operator_decision is True
                        else ("denied" if operator_decision is False else "resolved"),
                        policy_version="v1",
                        latency_ms=0.0,
                    )
                )
                reply_text = (
                    f"Action approved by operator: {case.target_action}"
                    if operator_decision is True
                    else (
                        f"Action denied by operator: {case.target_action}"
                        if operator_decision is False
                        else str(operator_decision)
                    )
                )
                return HubReply(
                    reply=reply_text,
                    case_ref=case.case_ref,
                    route=Route.HUMAN.value,
                )
            raise KeyError(f"no parked turn for ref {ref!r}")

        seen = self._logged_count()
        state = self._graph.invoke(
            Command(resume=operator_decision),
            config={
                "configurable": {
                    "thread_id": thread["thread_id"],
                    "session_token": thread["token"],
                }
            },
        )
        if case is not None:
            new_status = "refused" if operator_decision is False else "resolved"
            updated_case = OperatorQueueItem(
                case_ref=case.case_ref,
                persona=case.persona,
                status=new_status,
                reason_rule_id=case.reason_rule_id,
                created_at=case.created_at,
                customer_message=case.customer_message,
                entry_reference=case.entry_reference,
                amount=case.amount,
                currency=case.currency,
                target_action=case.target_action,
                awaiting_ref=case.awaiting_ref,
                gate_verdict=case.gate_verdict,
            )
            self._cases[case.case_ref] = updated_case
            if case.awaiting_ref:
                self._cases_by_ref[case.awaiting_ref] = updated_case

        self._deps.log.append(
            DecisionRecord(
                stage=Stage.HUMAN,
                session_ref=session_ref_for(thread["token"]),
                inputs_summary={
                    "actor_id": actor_id,
                    "case_ref": case.case_ref if case else ref,
                    "decision": str(operator_decision),
                    "justification": justification or "Operator resolved turn",
                },
                verdict="approved"
                if operator_decision is True
                else ("denied" if operator_decision is False else "resolved"),
                policy_version="v1",
                latency_ms=0.0,
            )
        )
        return self._reply_of(state, thread["thread_id"], self._turn_trace(seen))

    def _logged_count(self) -> int:
        """How many decision records the log holds right now.

        The log is an append-only jsonl, so counting means a full read; at
        demo volume that is cheap, and a production service would track the
        file offset instead.
        """
        return sum(1 for _ in self._deps.log)

    def _turn_trace(self, seen: int) -> tuple[TraceStep, ...]:
        """The decision records appended since ``seen``: this turn's trace."""
        steps = []
        for index, record in enumerate(self._deps.log):
            if index < seen:
                continue
            steps.append(
                TraceStep(
                    stage=record.stage.value,
                    rule_id=record.rule_id,
                    verdict=record.verdict,
                    scores=dict(record.scores),
                    summary=dict(record.inputs_summary),
                )
            )
        return tuple(steps)

    def _reply_of(
        self, state: dict[str, Any], thread_id: str, trace: tuple[TraceStep, ...] = ()
    ) -> HubReply:
        """Turn the graph's final (or paused) state into the app's reply."""
        route = state.get("route")
        interrupts = state.get("__interrupt__") or ()
        card = state.get("card")
        case_ref = state.get("case_ref")
        if interrupts:
            payload = interrupts[0].value
            awaiting_ref = str(case_ref or thread_id)
            # The operator resumes with the ref the interrupt handed them.
            self._threads[awaiting_ref] = self._threads[thread_id]
            if payload.get("type") == "approve_action":
                # FR-7: the confirmation card, mapped from the parked payload
                # (the Gate read the amount and currency from the bank).
                card = {
                    "key": "action_confirmation",
                    "payload": {
                        "action": payload.get("action"),
                        "entry_reference": payload.get("entry_reference"),
                        "amount": payload.get("amount"),
                        "currency": payload.get("currency"),
                    },
                }
                action_name = payload.get("action")
                target_act: (
                    Literal["cancel_payment", "retry_payment", "open_investigation"] | None
                ) = (
                    action_name
                    if action_name in ("cancel_payment", "retry_payment", "open_investigation")
                    else None
                )
                queue_item = OperatorQueueItem(
                    case_ref=case_ref or f"CASE-{state.get('persona', 'USER').upper()}-ACT",
                    persona=str(state.get("persona") or "unknown"),
                    status="pending_approval",
                    reason_rule_id=str(payload.get("rule_id") or "GATE-AMOUNT-LIMIT"),
                    created_at=datetime.now(UTC).isoformat(),
                    customer_message=str(state.get("message") or ""),
                    entry_reference=payload.get("entry_reference"),
                    amount=str(payload.get("amount"))
                    if payload.get("amount") is not None
                    else None,
                    currency=payload.get("currency"),
                    target_action=target_act,
                    awaiting_ref=awaiting_ref,
                    gate_verdict="ask",
                )
                self._cases[queue_item.case_ref] = queue_item
                self._cases_by_ref[awaiting_ref] = queue_item
            elif payload.get("type") == "operator_queue":
                queue_item = OperatorQueueItem(
                    case_ref=case_ref or f"CASE-{state.get('persona', 'USER').upper()}-ESC",
                    persona=str(state.get("persona") or "unknown"),
                    status="in_investigation",
                    reason_rule_id=str(state.get("escalate_reason") or "RT-NEEDS-PERSON"),
                    created_at=datetime.now(UTC).isoformat(),
                    customer_message=str(state.get("message") or ""),
                    entry_reference=state.get("entry_reference"),
                    amount=str(state.get("action_amount"))
                    if state.get("action_amount") is not None
                    else None,
                    currency=state.get("action_currency"),
                    target_action="open_investigation",
                    awaiting_ref=awaiting_ref,
                    gate_verdict=None,
                )
                self._cases[queue_item.case_ref] = queue_item
                self._cases_by_ref[awaiting_ref] = queue_item

            return HubReply(
                reply="",
                card=card,
                route=route.value if isinstance(route, Route) else None,
                case_ref=case_ref,
                escalated=True,
                awaiting=str(payload.get("type", "")),
                awaiting_ref=awaiting_ref,
                trace=trace,
            )

        if state.get("gate_verdict") == "block" or (card and card.get("key") == "refusal"):
            refusal_rule = str(
                state.get("rule_id")
                or (card.get("payload", {}).get("rule") if card else "")
                or "GATE-BLOCK"
            )
            blocked_ref = case_ref or f"CASE-{state.get('persona', 'USER').upper()}-BLOCK"
            action_name = state.get("action")
            target_act_blocked: (
                Literal["cancel_payment", "retry_payment", "open_investigation"] | None
            ) = (
                action_name
                if action_name in ("cancel_payment", "retry_payment", "open_investigation")
                else None
            )
            blocked_item = OperatorQueueItem(
                case_ref=blocked_ref,
                persona=str(state.get("persona") or "unknown"),
                status="refused",
                reason_rule_id=refusal_rule,
                created_at=datetime.now(UTC).isoformat(),
                customer_message=str(state.get("message") or ""),
                entry_reference=state.get("entry_reference"),
                amount=str(state.get("action_amount"))
                if state.get("action_amount") is not None
                else None,
                currency=state.get("action_currency"),
                target_action=target_act_blocked,
                awaiting_ref=blocked_ref,
                gate_verdict="block",
            )
            self._cases[blocked_item.case_ref] = blocked_item
            self._cases_by_ref[blocked_ref] = blocked_item

        return HubReply(
            reply=str(state.get("reply") or ""),
            card=state.get("card"),
            route=route.value if isinstance(route, Route) else None,
            case_ref=state.get("case_ref"),
            escalated=bool(state.get("escalated")),
            trace=trace,
        )
