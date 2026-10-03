"""Tests for the demo decision core: score mapping, verdicts and the log append.

The scripted probability sets are chosen against the policy/v1.yaml thresholds
so each one lands on exactly one route rule: RT-ACT needs needs_human < 0.30
with clear >= 0.50 and confidence >= 0.60; RT-ESCALATE needs needs_human >=
0.70; RT-OUT-OF-SCOPE needs the out-of-scope option >= 0.60 while
dispute+fraud stays below 0.50.
"""

from __future__ import annotations

import pytest

from calvino.api.decide import DEMO_SESSION_TOKEN, run_demo_decision, scores_from_answers
from calvino.classifiers import LayaAnswer, workflow_questions
from calvino.decision_log import DecisionLog, read_records
from calvino.records import HumanAction, Route, session_ref_for

_STUCK = {
    "stuck payment": 0.90,
    "dispute or unrecognised charge": 0.03,
    "fraud or stolen access": 0.02,
    "other banking": 0.03,
    "out of scope": 0.02,
}
_AUTOPILOT = {
    "intent": {
        "check status": 0.90,
        "cancel transfer": 0.02,
        "retry payment": 0.02,
        "open a case": 0.02,
        "check case status": 0.02,
        "talk to a person": 0.02,
    },
    "clear_enough": {"clear": 0.95, "unclear": 0.05},
    "needs_human": {"human needed": 0.10, "can handle automatically": 0.90},
    "injection": {"risky": 0.02, "not risky": 0.98},
}

ACT_SCRIPT = {"workflow_area": _STUCK, **_AUTOPILOT}
ESCALATE_SCRIPT = {
    **ACT_SCRIPT,
    "needs_human": {"human needed": 0.95, "can handle automatically": 0.05},
}
OUT_OF_SCOPE_SCRIPT = {
    **ACT_SCRIPT,
    "workflow_area": {**_STUCK, "stuck payment": 0.05, "other banking": 0.10, "out of scope": 0.80},
}
# Everything scripted except the intent question: its uniform probabilities
# drag the aggregate confidence to 1/6, below min_confidence (0.60).
UNCLEAR_SCRIPT = {key: value for key, value in ACT_SCRIPT.items() if key != "intent"}


def answers_dict(script: dict[str, dict[str, float]]) -> dict[str, LayaAnswer]:
    """Build a complete answer set from a probability script."""
    answers = {}
    for question_id, question in workflow_questions().items():
        keys = list(question["criteria"].keys())
        probs = script.get(question_id) or {key: 1.0 / len(keys) for key in keys}
        total = sum(probs.values())
        probs = {key: round(value / total, 4) for key, value in probs.items()}
        answers[question_id] = LayaAnswer(
            question_id=question_id,
            chosen_option=max(probs, key=probs.get),
            probabilities=probs,
            confidence=max(probs.values()),
        )
    return answers


def test_scores_map_option_probabilities():
    scores = scores_from_answers(answers_dict(ACT_SCRIPT))
    assert scores["needs_human"] == pytest.approx(0.10)
    assert scores["clear_enough"] == pytest.approx(0.95)
    assert scores["injection"] == pytest.approx(0.02)
    assert scores["workflow_out_of_scope"] == pytest.approx(0.02)
    assert scores["workflow_dispute_or_fraud"] == pytest.approx(0.05)
    # The aggregate confidence is the most conservative one: the minimum.
    assert scores["confidence"] == pytest.approx(0.90)


def test_scores_reject_incomplete_answers():
    incomplete = answers_dict(ACT_SCRIPT)
    del incomplete["needs_human"]
    with pytest.raises(ValueError, match="incomplete laya answers"):
        scores_from_answers(incomplete)


def test_demo_decision_acts_and_logs(fake_loader_factory, policy, tmp_path):
    log = DecisionLog(tmp_path / "decisions.jsonl")
    loader = fake_loader_factory(ACT_SCRIPT)

    decision = run_demo_decision("mi transferencia sigue pendiente", loader, policy, log)

    assert decision.route is Route.AGENTS
    assert decision.rule_id == "RT-ACT"
    assert decision.human_action is HumanAction.NONE
    assert decision.policy_version == "v1"
    assert set(decision.answers) == set(workflow_questions())

    records = list(read_records(log.path))
    assert len(records) == 1
    assert records[0].rule_id == "RT-ACT"
    assert records[0].session_ref == session_ref_for(DEMO_SESSION_TOKEN)


def test_demo_decision_escalates_to_a_human(fake_loader_factory, policy, tmp_path):
    log = DecisionLog(tmp_path / "decisions.jsonl")
    loader = fake_loader_factory(ESCALATE_SCRIPT)

    decision = run_demo_decision("hablar con una persona ya", loader, policy, log)

    assert decision.route is Route.HUMAN
    assert decision.rule_id == "RT-ESCALATE"
    assert decision.human_action is HumanAction.FULL_TRANSFER


def test_demo_decision_detects_out_of_scope(fake_loader_factory, policy, tmp_path):
    log = DecisionLog(tmp_path / "decisions.jsonl")
    loader = fake_loader_factory(OUT_OF_SCOPE_SCRIPT)

    decision = run_demo_decision("receta de cocina", loader, policy, log)

    assert decision.route is Route.OUT_OF_SCOPE
    assert decision.rule_id == "RT-OUT-OF-SCOPE"


def test_demo_decision_clarifies_on_low_confidence(fake_loader_factory, policy, tmp_path):
    log = DecisionLog(tmp_path / "decisions.jsonl")
    loader = fake_loader_factory(UNCLEAR_SCRIPT)

    decision = run_demo_decision("hola", loader, policy, log)

    assert decision.route is Route.CLARIFY
    assert decision.rule_id == "RT-CLARIFY-CONFIDENCE"


def test_demo_decision_payload_never_carries_act_probability(fake_loader_factory, policy, tmp_path):
    # act_probability carries no signal (DESIGN 4.3 rule 6); TSD-005 strips it
    # at parse time, and nothing downstream may reintroduce it.
    log = DecisionLog(tmp_path / "decisions.jsonl")
    loader = fake_loader_factory(ACT_SCRIPT)

    decision = run_demo_decision("mi pago no llega", loader, policy, log)

    assert "act_probability" not in decision.model_dump_json()


def test_demo_decisions_append_in_order(fake_loader_factory, policy, tmp_path):
    log = DecisionLog(tmp_path / "decisions.jsonl")
    loader = fake_loader_factory(ACT_SCRIPT)

    first = run_demo_decision("uno", loader, policy, log)
    second = run_demo_decision("dos", loader, policy, log)

    records = list(read_records(log.path))
    assert [record.decision_id for record in records] == [
        first.decision_id,
        second.decision_id,
    ]
