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
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict, Field

from calvino.hub.graph import HubDependencies, build_hub_graph
from calvino.records import Route


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

    def resume(self, ref: str, operator_decision: Any) -> HubReply:
        """Continue a parked turn with the operator's decision.

        ``ref`` is what the interrupt handed the operator: the case ref for
        the operator queue, the thread ref for an action approval. An unknown
        ref raises instead of guessing a thread (fail closed).
        """
        thread = self._threads.get(ref)
        if thread is None:
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
        if interrupts:
            payload = interrupts[0].value
            case_ref = state.get("case_ref")
            awaiting_ref = str(case_ref or thread_id)
            # The operator resumes with the ref the interrupt handed them.
            self._threads[awaiting_ref] = self._threads[thread_id]
            card = state.get("card")
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
        return HubReply(
            reply=str(state.get("reply") or ""),
            card=state.get("card"),
            route=route.value if isinstance(route, Route) else None,
            case_ref=state.get("case_ref"),
            escalated=bool(state.get("escalated")),
            trace=trace,
        )
