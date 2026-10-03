"""The verification cascade (TSD-004): code checks, then Laya, then one batched judge call.

The fixed behaviour from the spec and DESIGN.md 4.4:

- Cascade order is cheapest-first by checker, but every tier still runs after a
  failure: the retry feedback is more useful when it names every failed
  criterion, not just the cheapest one.
- Aggregation is a fixed rule: any failed criterion fails the output. A timeout
  or error in a model tier counts as a failure of that tier's criteria (fail
  closed); an error inside the deterministic code checks is a bug and raises.
- On failure: retry once with the failed criteria as feedback, then escalate
  with the failed criteria in the case file.
- Every attempt is logged as a ``DecisionRecord`` with the rubric and prompt
  versions, carrying criterion ids only: the log never receives reply content.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence

from pydantic import BaseModel, ConfigDict

from calvino.decision_log import DecisionLog
from calvino.records import DecisionRecord, Stage, Versions
from calvino.verifier.code_checks import run_code_checks
from calvino.verifier.evidence import Evidence
from calvino.verifier.judge import JUDGE_PROMPT_VERSION, Judge, MockJudge
from calvino.verifier.laya_checks import FakeLayaChecker, LayaChecker
from calvino.verifier.rubric import CheckerKind, Criterion, Rubric, load_rubric
from calvino.verifier.verdicts import CriterionVerdict, VerificationResult

# Regenerates the output using the failed criteria as feedback (the hub's LLM
# stage). The returned text is verified again, exactly once.
Regenerate = Callable[[list[CriterionVerdict]], str]


class VerificationOutcome(BaseModel):
    """What the hub acts on: the final result, and whether to escalate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    result: VerificationResult
    escalated: bool

    def case_file_entries(self) -> list[dict[str, str]]:
        """The failed criteria for the escalation case file (AC-7)."""
        return [
            {"criterion_id": v.criterion_id, "checker": v.checker.value, "reason": v.reason}
            for v in self.result.failed_verdicts()
        ]


class Verifier:
    """Runs the cascade over one output, retries once, escalates, logs.

    Without explicit checkers the model tiers default to the scripted fakes, so
    the verifier is usable in demos and tests without any provider. With a log,
    every attempt is written to ``decisions.jsonl``.
    """

    def __init__(
        self,
        rubric: Rubric | None = None,
        laya_checker: LayaChecker | None = None,
        judge: Judge | None = None,
        log: DecisionLog | None = None,
        session_ref: str | None = None,
    ) -> None:
        if log is not None and session_ref is None:
            raise ValueError("a session_ref is required to log verdicts")
        self.rubric = rubric or load_rubric()
        self.laya_checker = laya_checker or FakeLayaChecker()
        self.judge = judge or MockJudge()
        self.log = log
        self.session_ref = session_ref

    def verify(self, output: str, evidence: Evidence) -> VerificationResult:
        """One verification attempt: every tier runs, verdicts come back in rubric order."""
        verdicts: list[CriterionVerdict] = []
        verdicts.extend(run_code_checks(self.rubric, output, evidence))
        verdicts.extend(
            self._run_tier(
                CheckerKind.LAYA,
                lambda criteria: self.laya_checker.check(output, evidence, criteria),
                self.rubric.criteria_for(CheckerKind.LAYA),
                "laya check failed",
            )
        )
        verdicts.extend(
            self._run_tier(
                CheckerKind.JUDGE,
                lambda criteria: self.judge.judge_batch(output, evidence, criteria),
                self.rubric.criteria_for(CheckerKind.JUDGE),
                "judge call failed",
            )
        )
        order = {criterion.id: index for index, criterion in enumerate(self.rubric.criteria)}
        verdicts.sort(key=lambda verdict: order[verdict.criterion_id])
        return VerificationResult(
            passed=all(verdict.passed for verdict in verdicts),
            verdicts=verdicts,
            rubric_ref=self.rubric.ref,
            attempts=1,
        )

    def run(
        self,
        output: str,
        evidence: Evidence,
        regenerate: Regenerate | None = None,
    ) -> VerificationOutcome:
        """Verify, retry once with the failed criteria as feedback, then escalate."""
        first = self._attempt(output, evidence, attempt=1)
        if first.passed:
            return VerificationOutcome(result=first, escalated=False)
        if regenerate is None:
            return VerificationOutcome(result=first, escalated=True)
        try:
            retry_output = regenerate(first.failed_verdicts())
        except Exception:
            # A regeneration that errors leaves nothing to verify: escalate with
            # the first attempt's failed criteria (fail closed).
            return VerificationOutcome(result=first, escalated=True)
        second = self._attempt(retry_output, evidence, attempt=2).model_copy(update={"attempts": 2})
        return VerificationOutcome(result=second, escalated=not second.passed)

    def _attempt(self, output: str, evidence: Evidence, attempt: int) -> VerificationResult:
        started = time.perf_counter()
        result = self.verify(output, evidence)
        self._log(result, attempt=attempt, latency_ms=(time.perf_counter() - started) * 1000)
        return result

    def _run_tier(
        self,
        kind: CheckerKind,
        call: Callable[[Sequence[Criterion]], list[CriterionVerdict]],
        criteria: Sequence[Criterion],
        failure_reason: str,
    ) -> list[CriterionVerdict]:
        """Run one model tier; a timeout, error or malformed answer fails its criteria."""
        if not criteria:
            return []
        expected = [criterion.id for criterion in criteria]
        try:
            verdicts = call(criteria)
            if [verdict.criterion_id for verdict in verdicts] != expected:
                raise ValueError("checker returned verdicts for the wrong criteria")
        except Exception as error:
            return [
                CriterionVerdict(
                    criterion_id=criterion.id,
                    passed=False,
                    checker=kind,
                    reason=f"{failure_reason}: {type(error).__name__}",
                )
                for criterion in criteria
            ]
        return verdicts

    def _log(self, result: VerificationResult, attempt: int, latency_ms: float) -> None:
        if self.log is None:
            return
        failed = [verdict.criterion_id for verdict in result.failed_verdicts()]
        # The record stays small without losing information: because the
        # cascade has no fall-through, the checker that decided any criterion
        # is fixed by the logged rubric version (criterion -> checker in
        # rubrics/*.yaml), so per-checker analysis derives from rubric_ref
        # plus the failed ids below.
        self.log.append(
            DecisionRecord(
                stage=Stage.VERIFIER,
                session_ref=self.session_ref or "",
                inputs_summary={
                    "attempt": attempt,
                    "criteria_total": len(result.verdicts),
                    "failed_criteria": ",".join(failed),
                },
                rule_id=",".join(failed) or None,
                # The verifier reads the rubric and the prompt template, not the
                # policy module; the rubric ref is its versioned decision input.
                policy_version=self.rubric.ref,
                verdict="pass" if result.passed else "fail",
                latency_ms=latency_ms,
                versions=Versions(rubric=result.rubric_ref, prompt=str(JUDGE_PROMPT_VERSION)),
            )
        )
