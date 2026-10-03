"""The Laya check interface (TSD-004): grounding criteria decided by System One.

The two Laya criteria of the customer-answer rubric (no money-movement promise,
factual claims grounded) are simple yes/no grounding questions: the real
implementation asks them through the TSD-005 ``QuestionBuilder`` and gates the
calibrated probabilities with the versioned policy. Until that lands, and in
every test, checks go through this interface and ``FakeLayaChecker`` (spec:
"Laya checks go through an interface that is faked in tests").
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from calvino.verifier.evidence import Evidence
from calvino.verifier.rubric import CheckerKind, Criterion
from calvino.verifier.verdicts import CriterionVerdict


class LayaChecker(Protocol):
    """Decides the rubric's Laya criteria with calibrated probabilities."""

    def check(
        self, output: str, evidence: Evidence, criteria: Sequence[Criterion]
    ) -> list[CriterionVerdict]:
        """One pass/fail verdict with a short reason per criterion."""
        ...


class FakeLayaChecker:
    """The test and demo Laya checker: scripted verdicts, records what it was asked.

    ``calls`` keeps the criterion ids of every call, so cascade tests can prove
    the Laya tier only ever sees the rubric's Laya criteria.
    """

    def __init__(
        self,
        verdicts: dict[str, tuple[bool, str]] | None = None,
        default: tuple[bool, str] = (True, "fake laya: no scripted verdict"),
    ) -> None:
        self.verdicts = dict(verdicts or {})
        self.default = default
        self.calls: list[list[str]] = []

    def check(
        self, output: str, evidence: Evidence, criteria: Sequence[Criterion]
    ) -> list[CriterionVerdict]:
        self.calls.append([criterion.id for criterion in criteria])
        results = []
        for criterion in criteria:
            passed, reason = self.verdicts.get(criterion.id, self.default)
            results.append(
                CriterionVerdict(
                    criterion_id=criterion.id,
                    passed=passed,
                    checker=CheckerKind.LAYA,
                    reason=reason,
                )
            )
        return results
