"""Tests for the verification cascade (TSD-004): order, errors, retry, escalation, logging."""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from calvino.decision_log import DecisionLog, read_records
from calvino.records import Stage, session_ref_for
from calvino.tools.contracts import TransactionStatus
from calvino.verifier.cascade import VerificationOutcome, Verifier
from calvino.verifier.evidence import Evidence
from calvino.verifier.judge import JUDGE_PROMPT_VERSION, MockJudge, NotRunJudge
from calvino.verifier.laya_checks import FakeLayaChecker
from calvino.verifier.rubric import V1_RUBRIC_PATH, CheckerKind, Criterion, load_rubric
from calvino.verifier.verdicts import CriterionVerdict

CLEAN_REPLY = "Su pago de 1,500.00 MXN sigue pendiente."

EVIDENCE = Evidence(
    amounts=frozenset({Decimal("1500.00")}),
    dates=frozenset({date(2026, 9, 28)}),
    merchants=frozenset({"Aeromexico vacaciones"}),
    statuses=frozenset({TransactionStatus.PENDING}),
    customer_language="es",
)


# Rubric v1 still has two Laya-tier criteria, so the tier mechanics (call recording, errors,
# scripted failures) are tested against it. The shipped default is v2, which assigns no
# criterion to a tier without an implementation.
V1 = load_rubric(V1_RUBRIC_PATH)


def _criteria_for(kind: CheckerKind, rubric=None) -> list[Criterion]:
    return (rubric or load_rubric()).criteria_for(kind)


class FlakyJudge:
    """Fails the first call, passes every later call: drives the retry path."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def judge_batch(self, output, evidence, criteria):
        self.calls.append([criterion.id for criterion in criteria])
        passed = len(self.calls) > 1
        return [
            CriterionVerdict(
                criterion_id=criterion.id,
                passed=passed,
                checker=CheckerKind.JUDGE,
                reason="flaky judge",
            )
            for criterion in criteria
        ]


class BrokenJudge:
    """Raises on every call: a timeout or transport error, counted as a failure."""

    def judge_batch(self, output, evidence, criteria):
        raise TimeoutError("judge timed out")


class WrongIdsJudge:
    """Returns verdicts for criteria it was not asked about: a malformed answer."""

    def judge_batch(self, output, evidence, criteria):
        return [
            CriterionVerdict(
                criterion_id="not-asked", passed=True, checker=CheckerKind.JUDGE, reason="x"
            )
        ]


def test_clean_output_passes_every_tier():
    verifier = Verifier(laya_checker=FakeLayaChecker(), judge=MockJudge())
    result = verifier.verify(CLEAN_REPLY, EVIDENCE)
    assert result.passed
    assert result.attempts == 1
    rubric = load_rubric()
    assert [v.criterion_id for v in result.verdicts] == [c.id for c in rubric.criteria]
    checker_by_id = {c.id: c.checker for c in rubric.criteria}
    assert all(v.checker is checker_by_id[v.criterion_id] for v in result.verdicts)


def test_code_criteria_never_reach_laya_or_the_judge_and_the_judge_runs_once():
    laya = FakeLayaChecker()
    judge = MockJudge()
    Verifier(rubric=V1, laya_checker=laya, judge=judge).verify(CLEAN_REPLY, EVIDENCE)
    assert judge.calls == [[c.id for c in _criteria_for(CheckerKind.JUDGE, V1)]]
    assert laya.calls == [[c.id for c in _criteria_for(CheckerKind.LAYA, V1)]]
    code_ids = {c.id for c in _criteria_for(CheckerKind.CODE, V1)}
    assert not code_ids & set(judge.calls[0])
    assert not code_ids & set(laya.calls[0])


def test_a_failed_code_check_fails_the_whole_output():
    verifier = Verifier()
    result = verifier.verify("Le devolvimos 9,999.00 MXN hoy.", EVIDENCE)
    assert not result.passed
    failed_ids = {v.criterion_id for v in result.failed_verdicts()}
    assert "amounts-dates-merchants-match" in failed_ids


def test_a_scripted_laya_failure_fails_the_output():
    laya = FakeLayaChecker(verdicts={"no-money-movement-promise": (False, "promises a refund")})
    result = Verifier(rubric=V1, laya_checker=laya).verify(CLEAN_REPLY, EVIDENCE)
    assert not result.passed
    assert any(
        v.criterion_id == "no-money-movement-promise" and v.checker is CheckerKind.LAYA
        for v in result.failed_verdicts()
    )


def test_a_judge_error_counts_as_a_failure_of_its_criteria():
    result = Verifier(judge=BrokenJudge()).verify(CLEAN_REPLY, EVIDENCE)
    assert not result.passed
    judge_ids = {c.id for c in _criteria_for(CheckerKind.JUDGE)}
    failed = {v.criterion_id: v for v in result.failed_verdicts()}
    assert judge_ids <= set(failed)
    assert all("judge call failed: TimeoutError" in failed[i].reason for i in judge_ids)


def test_a_judge_returning_wrong_ids_counts_as_a_failure():
    result = Verifier(judge=WrongIdsJudge()).verify(CLEAN_REPLY, EVIDENCE)
    assert not result.passed
    assert all(
        "judge call failed: ValueError" in v.reason
        for v in result.failed_verdicts()
        if v.checker is CheckerKind.JUDGE
    )


def test_a_laya_error_counts_as_a_failure_of_its_criteria():
    class BrokenLaya:
        def check(self, output, evidence, criteria):
            raise RuntimeError("laya unavailable")

    result = Verifier(rubric=V1, laya_checker=BrokenLaya()).verify(CLEAN_REPLY, EVIDENCE)
    assert not result.passed
    assert any("laya check failed: RuntimeError" in v.reason for v in result.failed_verdicts())


def test_retry_once_with_the_failed_criteria_as_feedback_then_pass():
    judge = FlakyJudge()
    feedback: list[list[str]] = []

    def regenerate(failed):
        feedback.append([v.criterion_id for v in failed])
        return "Su pago de 1,500.00 MXN sigue pendiente, gracias."

    outcome = Verifier(judge=judge).run(CLEAN_REPLY, EVIDENCE, regenerate)
    assert outcome.result.passed
    assert outcome.result.attempts == 2
    assert not outcome.escalated
    judge_ids = [c.id for c in _criteria_for(CheckerKind.JUDGE)]
    assert feedback == [judge_ids]
    assert judge.calls == [judge_ids, judge_ids]


def test_retry_then_escalation_with_the_failed_criteria(tmp_path):
    judge = MockJudge(verdicts={"no-invented-policy": (False, "invented a fee waiver rule")})
    outcome = Verifier(judge=judge).run(CLEAN_REPLY, EVIDENCE, lambda failed: CLEAN_REPLY)
    assert not outcome.result.passed
    assert outcome.result.attempts == 2
    assert outcome.escalated
    entries = outcome.case_file_entries()
    assert {
        "criterion_id": "no-invented-policy",
        "checker": "judge",
        "reason": "invented a fee waiver rule",
    } in entries


def test_without_a_regenerate_a_failure_escalates_immediately():
    judge = MockJudge(verdicts={"question-fully-answered": (False, "gap not stated")})
    outcome = Verifier(judge=judge).run(CLEAN_REPLY, EVIDENCE)
    assert outcome.escalated
    assert outcome.result.attempts == 1
    assert len(judge.calls) == 1


def test_a_regenerate_error_escalates_with_the_first_result():
    judge = MockJudge(verdicts={"question-fully-answered": (False, "gap not stated")})

    def regenerate(failed):
        raise RuntimeError("llm unavailable")

    outcome = Verifier(judge=judge).run(CLEAN_REPLY, EVIDENCE, regenerate)
    assert outcome.escalated
    assert outcome.result.attempts == 1
    assert [v.criterion_id for v in outcome.result.failed_verdicts()] == ["question-fully-answered"]


def test_a_passing_run_logs_one_record_with_the_versions(tmp_path):
    log = DecisionLog(tmp_path / "decisions.jsonl")
    verifier = Verifier(judge=MockJudge(), log=log, session_ref=session_ref_for("demo-token"))
    outcome = verifier.run(CLEAN_REPLY, EVIDENCE)
    assert not outcome.escalated
    records = list(read_records(log.path))
    assert len(records) == 1
    record = records[0]
    assert record.stage is Stage.VERIFIER
    assert record.verdict == "pass"
    assert record.policy_version == "customer-answer@2"
    assert record.versions.rubric == "customer-answer@2"
    assert record.versions.prompt == str(JUDGE_PROMPT_VERSION)
    assert record.rule_id is None


def test_a_retrying_run_logs_both_attempts_without_reply_content(tmp_path):
    log = DecisionLog(tmp_path / "decisions.jsonl")
    judge = FlakyJudge()
    verifier = Verifier(judge=judge, log=log, session_ref=session_ref_for("demo-token"))
    verifier.run(CLEAN_REPLY, EVIDENCE, lambda failed: CLEAN_REPLY)
    records = list(read_records(log.path))
    assert [r.verdict for r in records] == ["fail", "pass"]
    assert records[0].inputs_summary["attempt"] == 1
    assert records[1].inputs_summary["attempt"] == 2
    failed_criteria = records[0].inputs_summary["failed_criteria"]
    assert set(failed_criteria.split(",")) == {c.id for c in _criteria_for(CheckerKind.JUDGE)}
    # The log carries criterion ids and counts, never the reply itself.
    for record in records:
        assert all(CLEAN_REPLY not in str(value) for value in record.inputs_summary.values())


def test_logging_requires_a_session_ref(tmp_path):
    with pytest.raises(ValueError, match="session_ref"):
        Verifier(log=DecisionLog(tmp_path / "decisions.jsonl"))


def test_outcome_is_a_frozen_model():
    outcome = VerificationOutcome.model_validate(
        {
            "result": {
                "passed": True,
                "verdicts": [
                    {
                        "criterion_id": "x",
                        "passed": True,
                        "checker": "code",
                        "reason": "ok",
                    }
                ],
                "rubric_ref": "customer-answer@1",
            },
            "escalated": False,
        }
    )
    with pytest.raises(ValidationError):
        outcome.escalated = True


def test_an_unconfigured_judge_fails_its_criteria_closed():
    # No silent default: with no judge the judged criteria are unverified, never passed.
    result = Verifier().verify(CLEAN_REPLY, EVIDENCE)
    assert not result.passed
    judge_ids = {c.id for c in _criteria_for(CheckerKind.JUDGE)}
    failed = {v.criterion_id: v for v in result.failed_verdicts()}
    assert judge_ids == set(failed)
    assert all("unverified: no judge checker is configured" in v.reason for v in failed.values())
    assert all(v.checker is CheckerKind.JUDGE for v in failed.values())


def test_an_unconfigured_laya_tier_fails_its_criteria_closed():
    result = Verifier(rubric=V1, judge=MockJudge()).verify(CLEAN_REPLY, EVIDENCE)
    assert not result.passed
    laya_ids = {c.id for c in _criteria_for(CheckerKind.LAYA, V1)}
    failed = {v.criterion_id: v for v in result.failed_verdicts()}
    assert laya_ids == set(failed)
    assert all("unverified: no laya checker is configured" in v.reason for v in failed.values())


def test_the_shipped_rubric_needs_only_the_judge_beyond_code():
    # Rubric v2 has no Laya-tier criteria, so a judge alone fully verifies a clean reply.
    assert Verifier(judge=MockJudge()).verify(CLEAN_REPLY, EVIDENCE).passed


def test_the_not_run_judge_passes_by_name_not_in_silence():
    judge = NotRunJudge()
    verdicts = judge.judge_batch(CLEAN_REPLY, EVIDENCE, _criteria_for(CheckerKind.JUDGE))
    assert verdicts and all(v.passed for v in verdicts)
    assert all(v.reason == "not run: keyless demo, template reply" for v in verdicts)
    assert Verifier(judge=judge).verify(CLEAN_REPLY, EVIDENCE).passed
