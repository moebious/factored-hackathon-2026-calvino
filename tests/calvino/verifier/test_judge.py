"""Tests for the judge interface (TSD-004): prompt, parser and MockJudge."""

import json

from calvino.verifier.evidence import Evidence
from calvino.verifier.judge import (
    JUDGE_PROMPT_VERSION,
    MockJudge,
    build_judge_prompt,
    parse_judge_response,
)
from calvino.verifier.rubric import CheckerKind, load_rubric

EVIDENCE = Evidence(customer_language="es", read_backs=frozenset({"cancel_transfer"}))


def _judge_criteria():
    return load_rubric().criteria_for(CheckerKind.JUDGE)


def _response(entries):
    return json.dumps({"verdicts": entries})


def test_prompt_contains_the_criteria_and_evidence():
    prompt = build_judge_prompt("Su pago sigue pendiente.", EVIDENCE, _judge_criteria())
    assert JUDGE_PROMPT_VERSION >= 1  # the version logged with every verdict
    for criterion in _judge_criteria():
        assert criterion.id in prompt
        assert criterion.text in prompt
    assert "cancel_transfer" in prompt  # evidence facts are rendered
    assert "es" in prompt
    assert "Su pago sigue pendiente." in prompt


def test_prompt_tells_the_judge_to_fail_when_unclear():
    prompt = build_judge_prompt("texto", EVIDENCE, _judge_criteria())
    lowered = prompt.casefold()
    assert "fail the criterion" in lowered
    assert "never pass a criterion you are unsure about" in lowered


def test_prompt_decomposes_criteria_into_checklists():
    criteria = _judge_criteria()
    prompt = build_judge_prompt("texto", EVIDENCE, criteria)
    # "The next step is valid for the payment status and any required
    # confirmation is stated clearly" splits on " and " into two items.
    assert "- The next step is valid for the payment status" in prompt
    assert "- any required confirmation is stated clearly" in prompt


def test_parser_returns_one_verdict_per_criterion_in_order():
    criteria = _judge_criteria()
    entries = [
        {"criterion_id": c.id, "passed": i % 2 == 0, "reason": f"reason {i}"}
        for i, c in enumerate(criteria)
    ]
    verdicts = parse_judge_response(_response(entries), criteria)
    assert [v.criterion_id for v in verdicts] == [c.id for c in criteria]
    assert [v.passed for v in verdicts] == [i % 2 == 0 for i in range(len(criteria))]
    assert all(v.checker is CheckerKind.JUDGE for v in verdicts)
    assert verdicts[0].reason == "reason 0"


def test_parser_accepts_a_fenced_json_response():
    criteria = _judge_criteria()
    entries = [{"criterion_id": c.id, "passed": True, "reason": "ok"} for c in criteria]
    fenced = f"```json\n{_response(entries)}\n```"
    assert all(v.passed for v in parse_judge_response(fenced, criteria))


def test_a_criterion_the_response_does_not_decide_fails():
    criteria = _judge_criteria()
    entries = [{"criterion_id": criteria[0].id, "passed": True, "reason": "ok"}]
    verdicts = parse_judge_response(_response(entries), criteria)
    assert verdicts[0].passed
    assert not verdicts[1].passed
    assert "no clear verdict" in verdicts[1].reason


def test_a_non_boolean_passed_fails():
    criteria = _judge_criteria()
    entries = [{"criterion_id": c.id, "passed": "yes", "reason": "ok"} for c in criteria]
    verdicts = parse_judge_response(_response(entries), criteria)
    assert all(not v.passed for v in verdicts)


def test_an_unreadable_response_fails_every_criterion():
    criteria = _judge_criteria()
    for broken in ("", "I think it passes", '{"verdicts": "all good"}', "[1, 2, 3]"):
        verdicts = parse_judge_response(broken, criteria)
        assert len(verdicts) == len(criteria)
        assert all(not v.passed for v in verdicts)
        assert all("could not be read" in v.reason for v in verdicts)


def test_a_missing_reason_still_yields_a_verdict():
    criteria = _judge_criteria()[:1]
    verdicts = parse_judge_response(
        _response([{"criterion_id": criteria[0].id, "passed": False}]), criteria
    )
    assert not verdicts[0].passed
    assert verdicts[0].reason == "judge gave no reason"


def test_mock_judge_returns_scripted_verdicts_and_records_calls():
    judge = MockJudge(
        verdicts={"no-invented-policy": (False, "invented a fee waiver rule")},
        default=(True, "looks fine"),
    )
    criteria = _judge_criteria()
    verdicts = judge.judge_batch("texto", EVIDENCE, criteria)
    assert judge.calls == [[c.id for c in criteria]]
    by_id = {v.criterion_id: v for v in verdicts}
    assert not by_id["no-invented-policy"].passed
    assert by_id["no-invented-policy"].reason == "invented a fee waiver rule"
    assert by_id["question-fully-answered"].passed
    assert all(v.checker is CheckerKind.JUDGE for v in verdicts)
