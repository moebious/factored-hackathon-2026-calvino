"""Tests for the verdict types (TSD-004): the fixed aggregation rule and the helpers."""

import pytest
from pydantic import ValidationError

from calvino.verifier import CheckerKind, CriterionVerdict, VerificationResult

PASS = CriterionVerdict(
    criterion_id="amounts-dates-merchants-match",
    passed=True,
    checker=CheckerKind.CODE,
    reason="every stated amount appears in a tool result",
)
FAIL = CriterionVerdict(
    criterion_id="no-invented-policy",
    passed=False,
    checker=CheckerKind.JUDGE,
    reason="the reply invents an eligibility rule not in the policy documents",
)


def test_all_pass_result_passes():
    result = VerificationResult(
        passed=True, verdicts=[PASS], rubric_ref="customer-answer@1", attempts=1
    )
    assert result.passed
    assert result.failed_verdicts() == []


def test_any_failed_verdict_fails_the_result():
    result = VerificationResult(
        passed=False, verdicts=[PASS, FAIL], rubric_ref="customer-answer@1", attempts=2
    )
    assert not result.passed
    assert result.failed_verdicts() == [FAIL]


def test_passed_true_with_a_failed_verdict_is_rejected():
    # The aggregation is a fixed rule; a result cannot claim to pass with a failure inside.
    with pytest.raises(ValidationError, match="every criterion verdict"):
        VerificationResult(passed=True, verdicts=[PASS, FAIL], rubric_ref="customer-answer@1")


def test_passed_false_with_all_passing_verdicts_is_rejected():
    with pytest.raises(ValidationError, match="every criterion verdict"):
        VerificationResult(passed=False, verdicts=[PASS], rubric_ref="customer-answer@1")


def test_verdict_needs_a_reason():
    with pytest.raises(ValidationError):
        CriterionVerdict(criterion_id="c", passed=False, checker=CheckerKind.CODE, reason="")


def test_attempts_are_bounded():
    with pytest.raises(ValidationError):
        VerificationResult(passed=True, verdicts=[PASS], rubric_ref="r@1", attempts=3)


def test_result_is_immutable():
    result = VerificationResult(passed=True, verdicts=[PASS], rubric_ref="r@1")
    with pytest.raises(ValidationError):
        result.passed = False  # type: ignore[misc]
