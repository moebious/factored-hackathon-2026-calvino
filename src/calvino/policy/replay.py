"""Policy replay: re-run a logged decision from its ``DecisionRecord`` (AC-8, T-408).

The record holds every input the policy read, so a decision can be recomputed under the policy
version it was made with, or under a new one to see which verdicts would change.
"""

from __future__ import annotations

from calvino.policy.config import Policy
from calvino.policy.gate import GateDecision, decide_gate
from calvino.policy.route import RouteDecision, decide_route
from calvino.records import DecisionRecord


def replay_decision(record: DecisionRecord, policy: Policy) -> RouteDecision | GateDecision:
    """Recompute the decision a record describes. Raises ``ValueError`` for records the policy
    did not write (no ``decision_kind``)."""
    summary = record.inputs_summary
    facts: dict[str, object] = {
        key.removeprefix("fact."): value
        for key, value in summary.items()
        if key.startswith("fact.")
    }
    facts.setdefault("session_ref", record.session_ref)
    scores: dict[str, object] = dict(record.scores)
    kind = summary.get("decision_kind")
    if kind == "route":
        return decide_route(scores, facts, policy)
    if kind == "gate":
        action: dict[str, object] = {
            key.removeprefix("action."): value
            for key, value in summary.items()
            if key.startswith("action.")
        }
        return decide_gate(action, scores, facts, policy)
    raise ValueError(f"record {record.decision_id} was not written by the policy engine")
