"""Tests for policy v4 (TSD-030, T-209): route confidence calibrated to 5-class distribution.

v4 aligns route.min_confidence to 0.50 for the 5-class workflow_area distribution, resolving the
contradiction where stuck payments in [0.50, 0.60) passed min_stuck_payment: 0.50 but were
blocked by RT-CLARIFY-CONFIDENCE.

The Gate's own thresholds (min_confidence: 0.60, min_clear_enough: 0.70) and hard rules remain
completely unchanged and continue guarding all consequential writes.
Released policy files (v1, v2, v3) must replay unchanged. No model calls, network or dataset.
"""

from __future__ import annotations

from pathlib import Path

from calvino.policy import (
    DEFAULT_POLICY_PATH,
    ActionName,
    GateAction,
    decide_gate,
    load_policy,
)
from calvino.policy.route import decide_route
from calvino.records import GateVerdict, Route, session_ref_for

POLICY_DIR = Path(__file__).resolve().parents[3] / "policy"
V1, V2, V3, V4 = (load_policy(POLICY_DIR / f"v{n}.yaml") for n in (1, 2, 3, 4))
REF = session_ref_for("synthetic-session-token-for-tests")

FACTS = {
    "session_ref": REF,
    "fraud_signal": False,
    "asks_for_human": False,
    "auth_failures": 0,
    "via_regulator": False,
    "vulnerable_customer": False,
}


def routine(**overrides):
    """Scores of a routine, concrete stuck-payment request."""
    base = {
        "needs_human": 0.90,
        "clear_enough": 0.05,
        "confidence": 0.80,
        "workflow_out_of_scope": 0.01,
        "workflow_dispute_or_fraud": 0.02,
        "workflow_stuck_payment": 0.95,
        "talk_to_person": 0.01,
        "injection": 0.10,
    }
    base.update(overrides)
    return base


def test_default_policy_is_v4():
    policy = load_policy()
    assert policy.version == "v4"
    assert DEFAULT_POLICY_PATH.name == "v4.yaml"


def test_released_policies_keep_their_behaviour():
    assert V1.version == "v1"
    assert V2.version == "v2"
    assert V3.version == "v3"
    assert V3.route.min_confidence == 0.60

    assert V4.version == "v4"
    assert V4.route.min_confidence == 0.50
    assert V4.route.min_stuck_payment == 0.50
    assert V4.route.confidence_source == "workflow_area"

    # Gate and hard rules in v4 are identical to v3/v2 (unweakened write protections).
    assert V4.gate == V3.gate and V4.hard_rules == V3.hard_rules


def test_stuck_payment_in_50_to_60_range_proceeds_in_v4_and_clarifies_in_v3():
    # Case representative of ORC-007 (0.5120) and ORC-008 (0.5914)
    scores = routine(workflow_stuck_payment=0.55, confidence=0.55)

    v3 = decide_route(scores, FACTS, V3)
    assert (v3.route, v3.rule_id) == (Route.CLARIFY, "RT-CLARIFY-CONFIDENCE")

    v4 = decide_route(scores, FACTS, V4)
    assert (v4.route, v4.rule_id) == (Route.AGENTS, "RT-ACT")


def test_confidence_below_50_still_clarifies_in_v4():
    scores = routine(workflow_stuck_payment=0.49, confidence=0.49)
    v4 = decide_route(scores, FACTS, V4)
    assert (v4.route, v4.rule_id) == (Route.CLARIFY, "RT-CLARIFY-NOT-STUCK")

    scores_low_conf = routine(workflow_stuck_payment=0.55, confidence=0.49)
    v4_conf = decide_route(scores_low_conf, FACTS, V4)
    assert (v4_conf.route, v4_conf.rule_id) == (Route.CLARIFY, "RT-CLARIFY-CONFIDENCE")


def test_gate_write_protection_is_strictly_preserved():
    # The Gate still demands min_confidence: 0.60 and min_clear_enough: 0.70 for writes
    action = GateAction(
        name=ActionName.REQUEST_CANCELLATION,
        transaction_status="pending",
        amount=100.0,
        currency="USD",
        owner_verified=True,
    )
    # A candidate write with confidence 0.55 (valid for route under v4) is still parked by the Gate
    candidate_scores = {
        "clear_enough": 0.85,
        "confidence": 0.55,  # below gate's 0.60
        "injection": 0.05,
    }
    gate_decision = decide_gate(action, candidate_scores, FACTS, V4)
    assert gate_decision.verdict == GateVerdict.ASK
    assert gate_decision.rule_id == "GATE-LOW-CONFIDENCE"
