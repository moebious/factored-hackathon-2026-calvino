"""Verifier verdict types (TSD-004): one verdict per criterion, one result per output.

Aggregation is a fixed rule, not a model: any failed criterion fails the output
(DESIGN.md 4.4, decision 14). ``VerificationResult`` enforces that rule in its
validator, so a result can never claim to pass while carrying a failed verdict.

Every verdict records the checker that decided it (code, Laya or judge), so the
end-to-end evaluation (T-303) can measure the false-pass rate per checker
against hand labels.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from calvino.verifier.rubric import CheckerKind


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CriterionVerdict(_Frozen):
    """One criterion's pass/fail verdict, with the short reason a human reads."""

    criterion_id: str = Field(min_length=1)
    passed: bool
    checker: CheckerKind
    reason: str = Field(min_length=1)


class VerificationResult(_Frozen):
    """The verification of one agent output: every verdict plus the fixed aggregation.

    ``attempts`` is 1 when the output passed first time and 2 when it passed (or
    finally failed) after the single retry with the failed criteria as feedback.
    """

    passed: bool
    verdicts: list[CriterionVerdict] = Field(min_length=1)
    rubric_ref: str = Field(min_length=1)
    attempts: int = Field(default=1, ge=1, le=2)

    @model_validator(mode="after")
    def _passed_matches_the_fixed_rule(self) -> VerificationResult:
        # Any failed criterion fails the output; a result that says otherwise is a bug.
        if self.passed != all(verdict.passed for verdict in self.verdicts):
            raise ValueError("passed must be true exactly when every criterion verdict passed")
        return self

    def failed_verdicts(self) -> list[CriterionVerdict]:
        """The failed verdicts, in rubric order: the retry feedback and case-file content."""
        return [verdict for verdict in self.verdicts if not verdict.passed]
