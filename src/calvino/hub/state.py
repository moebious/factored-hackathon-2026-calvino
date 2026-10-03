"""The hub's graph state (TSD-009): what the LangGraph nodes read and write.

Kept deliberately flat and small: the state is what the checkpointer
persists, so nothing sensitive lives here. The session token in particular
is never a state field (it stays inside the ``TrustedSessionIssuer``); the
state carries only the hashed ``session_ref``. Values that accumulate
across nodes (tool results, log-worthy events) use the ``operator.add``
reducer so parallel branches merge instead of overwriting.
"""

from __future__ import annotations

import operator
from enum import StrEnum
from typing import Annotated, Any, TypedDict

from calvino.policy import Facts
from calvino.records import HumanAction, Route
from calvino.verifier.evidence import ToolResult


class HubStage(StrEnum):
    """The five workflow stages plus the out-of-scope reply (DESIGN 6.1)."""

    EXPLAIN = "explain"
    CLARIFY = "clarify"
    ACT = "act"
    INVESTIGATE = "investigate"
    FOLLOW_UP = "follow_up"
    OUT_OF_SCOPE = "out_of_scope"


class HubState(TypedDict, total=False):
    """One customer request travelling through the graph.

    Identity: ``persona`` and ``session_ref`` (never a token, never a
    customer id from chat). Classification: ``message``, the calibrated
    ``scores``, the policy ``route`` and the ``rule_id`` that fired.
    Workflow: ``stage``, the focused transaction (``entry_reference`` and
    its ``status``), the requested ``action`` with its Gate fields
    (``gate_verdict``, ``action_amount``, ``action_currency``), the
    accumulated read ``tool_results``, the ``read_backs`` that confirm
    claimed actions, and the evidence built from them. Conversation: the
    agent's current ``draft``, the clarify ``question``, the final
    ``reply``, a ``case_ref`` when a human took over, and the fixed-card
    ``card`` (key plus payload) the app renders.
    """

    persona: str
    session_ref: str
    message: str
    facts: Facts | None
    scores: dict[str, float]
    route: Route | None
    rule_id: str | None
    human_action: HumanAction | None
    stage: HubStage
    entry_reference: str | None
    status: str | None
    action: str | None
    gate_verdict: str | None
    action_amount: str | None
    action_currency: str | None
    tool_results: Annotated[list[ToolResult], operator.add]
    read_backs: Annotated[list[str], operator.add]
    pending_calls: list[dict[str, Any]]
    tool_rounds: int
    draft: str | None
    question: str | None
    reply: str | None
    card: dict[str, Any] | None
    case_ref: str | None
    case_file: list[dict[str, str]]
    escalate_reason: str | None
    escalated: bool
