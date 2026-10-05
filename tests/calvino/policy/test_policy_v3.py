"""Tests for policy v3 (TSD-021): the route rebuilt on area, intent and injection.

v3 switches off the gates that measured at chance or blocked routine requests (needs_human, the
route's clear_enough, the minimum-over-all-answers confidence) and adds two (talk to a person,
stuck payment). Every switch defaults to the v1/v2 behaviour, so released policy files must
replay unchanged; both directions are tested. No model calls, network or dataset.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from calvino.api.decide import scores_from_answers
from calvino.classifiers import LayaAnswer
from calvino.policy import load_policy
from calvino.policy.route import decide_route, required_route_scores
from calvino.records import Route, session_ref_for

POLICY_DIR = Path(__file__).resolve().parents[3] / "policy"
V1, V2, V3 = (load_policy(POLICY_DIR / f"v{n}.yaml") for n in (1, 2, 3))
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
    """Scores of a routine, concrete stuck-payment request as live laya produces them."""
    base = {
        "needs_human": 0.90,  # live laya: high on routine requests [measured], AUROC 0.49
        "clear_enough": 0.05,  # live laya: low for messages that name no payment reference
        "confidence": 0.80,
        "workflow_out_of_scope": 0.01,
        "workflow_dispute_or_fraud": 0.02,
        "workflow_stuck_payment": 0.95,
        "talk_to_person": 0.01,
        "injection": 0.10,
    }
    base.update(overrides)
    return base


def test_the_released_policies_keep_their_behaviour():
    for policy in (V1, V2):
        rules = policy.route
        assert rules.use_needs_human is True
        assert rules.talk_to_person_at is None and rules.min_stuck_payment is None
        assert rules.confidence_source == "min_all"
        assert rules.min_clear_enough is not None
    assert V3.version == "v3"
    assert V3.route.use_needs_human is False and V3.route.min_clear_enough is None
    assert V3.route.talk_to_person_at == 0.5 and V3.route.min_stuck_payment == 0.5
    assert V3.route.confidence_source == "workflow_area"
    # The Gate and the hard rules are v2's, untouched.
    assert V3.gate == V2.gate and V3.hard_rules == V2.hard_rules


def test_a_routine_request_reaches_the_agent_under_v3_and_not_under_v2():
    scores = routine()
    v3 = decide_route(scores, FACTS, V3)
    assert (v3.route, v3.rule_id) == (Route.AGENTS, "RT-ACT")
    v2 = decide_route(scores, FACTS, V2)
    assert (v2.route, v2.rule_id) == (Route.HUMAN, "RT-ESCALATE")  # unchanged v2 behaviour


@pytest.mark.parametrize(
    ("override", "route", "rule_id"),
    [
        ({"workflow_dispute_or_fraud": 0.50}, Route.HUMAN, "RT-DISPUTE-FRAUD"),
        ({"workflow_out_of_scope": 0.60}, Route.OUT_OF_SCOPE, "RT-OUT-OF-SCOPE"),
        ({"injection": 0.50}, Route.HUMAN, "RT-INJECTION"),
        ({"talk_to_person": 0.50}, Route.HUMAN, "RT-TALK-TO-PERSON"),
        ({"workflow_stuck_payment": 0.49}, Route.CLARIFY, "RT-CLARIFY-NOT-STUCK"),
        ({"confidence": 0.59}, Route.CLARIFY, "RT-CLARIFY-CONFIDENCE"),
    ],
)
def test_v3_gates_fire_at_their_thresholds(override, route, rule_id):
    decision = decide_route(routine(**override), FACTS, V3)
    assert (decision.route, decision.rule_id) == (route, rule_id)


def test_just_below_each_v3_threshold_does_not_fire():
    below = routine(
        workflow_dispute_or_fraud=0.49,
        injection=0.49,
        talk_to_person=0.49,
        workflow_stuck_payment=0.5,
    )
    assert decide_route(below, FACTS, V3).route is Route.AGENTS


def test_v3_ignores_needs_human_and_clear_enough_entirely():
    for needs_human, clear in ((0.0, 1.0), (1.0, 0.0), (0.7, 0.0)):
        scores = routine(needs_human=needs_human, clear_enough=clear)
        assert decide_route(scores, FACTS, V3).rule_id == "RT-ACT"
    for name in ("needs_human", "clear_enough"):
        scores = routine()
        del scores[name]
        assert decide_route(scores, FACTS, V3).rule_id == "RT-ACT"  # not required under v3


@pytest.mark.parametrize("missing", ["talk_to_person", "workflow_stuck_payment", "confidence"])
def test_v3_fails_closed_when_a_score_it_reads_is_missing(missing):
    scores = routine()
    del scores[missing]
    decision = decide_route(scores, FACTS, V3)
    assert (decision.route, decision.rule_id) == (Route.HUMAN, "FC-SCORES")


def test_v1_and_v2_still_require_the_original_scores_only():
    scores = routine()
    del scores["talk_to_person"], scores["workflow_stuck_payment"]
    scores.update(needs_human=0.1, clear_enough=0.9)
    for policy in (V1, V2):
        assert decide_route(scores, FACTS, policy).rule_id == "RT-ACT"
    assert "needs_human" in required_route_scores(V2.route)
    assert "needs_human" not in required_route_scores(V3.route)
    assert {"talk_to_person", "workflow_stuck_payment"} <= set(required_route_scores(V3.route))


def test_hard_rules_still_win_under_v3():
    decision = decide_route(routine(), {**FACTS, "asks_for_human": True}, V3)
    assert (decision.route, decision.rule_id) == (Route.HUMAN, "HR-ASKS-HUMAN")


# -- scores_from_answers ------------------------------------------------------------------


def _answer(question_id, probabilities, confidence):
    chosen = max(probabilities, key=probabilities.get)
    return LayaAnswer(
        question_id=question_id,
        chosen_option=chosen,
        probabilities=probabilities,
        confidence=confidence,
    )


def laya_answers(intent_confidence=0.30):
    return {
        "workflow_area": _answer(
            "workflow_area",
            {
                "stuck payment": 0.90,
                "dispute or unrecognised charge": 0.04,
                "fraud or stolen access": 0.03,
                "other banking": 0.02,
                "out of scope": 0.01,
            },
            0.90,
        ),
        "intent": _answer(
            "intent",
            {
                "check status": 0.40,
                "cancel transfer": 0.10,
                "retry payment": 0.10,
                "open a case": 0.10,
                "check case status": 0.10,
                "talk to a person": 0.20,
            },
            intent_confidence,
        ),
        "clear_enough": _answer("clear_enough", {"clear": 0.05, "unclear": 0.95}, 0.95),
        "needs_human": _answer(
            "needs_human", {"human needed": 0.20, "can handle automatically": 0.80}, 0.80
        ),
        "injection": _answer("injection", {"risky": 0.10, "not risky": 0.90}, 0.90),
    }


def test_scores_expose_the_stuck_payment_and_talk_to_person_probabilities():
    scores = scores_from_answers(laya_answers())
    assert scores["workflow_stuck_payment"] == 0.90
    assert scores["talk_to_person"] == 0.20
    assert scores["workflow_dispute_or_fraud"] == pytest.approx(0.07)


def test_confidence_source_is_the_policys_choice():
    answers = laya_answers(intent_confidence=0.30)
    assert scores_from_answers(answers)["confidence"] == 0.30  # min over all five (v1, v2)
    assert scores_from_answers(answers, "min_all")["confidence"] == 0.30
    assert scores_from_answers(answers, "workflow_area")["confidence"] == 0.90  # v3


def test_a_routine_message_from_live_style_answers_reaches_the_agent_only_under_v3():
    answers = laya_answers()
    for policy, expected in ((V2, "RT-CLARIFY-CONFIDENCE"), (V3, "RT-ACT")):
        scores = scores_from_answers(answers, policy.route.confidence_source)
        assert decide_route(scores, FACTS, policy).rule_id == expected
