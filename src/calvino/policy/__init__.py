"""Policy engine (TSD-001): hard rules and the versioned thresholds that turn calibrated scores
into deterministic verdicts. No model calls; thresholds and limits live in the versioned policy
files (``policy/v3.yaml`` is the default; v1 and v2 stay for replay).
"""

from calvino.policy.config import DEFAULT_POLICY_PATH, Policy, load_policy
from calvino.policy.gate import GateDecision, decide_gate
from calvino.policy.inputs import ActionName, Facts, GateAction, Scores
from calvino.policy.replay import replay_decision
from calvino.policy.route import RouteDecision, decide_route

__all__ = [
    "DEFAULT_POLICY_PATH",
    "ActionName",
    "Facts",
    "GateAction",
    "GateDecision",
    "Policy",
    "RouteDecision",
    "Scores",
    "decide_gate",
    "decide_route",
    "load_policy",
    "replay_decision",
]
