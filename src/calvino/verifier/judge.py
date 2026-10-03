"""The LLM judge interface (TSD-004): one batched call labels the remaining criteria.

The provider is not chosen yet (decision 17): everything real lives behind the
``Judge`` protocol, and tests use ``MockJudge``. The prompt template is versioned
like the rubric and the policy; every logged verdict carries the rubric and the
prompt version it was made with, so verdicts replay.

The template decomposes each criterion into a checklist and instructs the judge
to fail when unclear: a false fail costs one retry, a false pass reaches the
customer (DESIGN.md 4.4). The parser fails closed: a criterion the response does
not decide, or a response that cannot be read at all, fails every criterion.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Protocol

from calvino.verifier.evidence import Evidence
from calvino.verifier.rubric import CheckerKind, Criterion
from calvino.verifier.verdicts import CriterionVerdict

# Bumped on any change to the template below; logged with every judge verdict.
JUDGE_PROMPT_VERSION = 1

_JUDGE_PROMPT_TEMPLATE = """\
You are a strict reviewer of one reply a bank's customer service is about to \
send to a customer. Decide every criterion listed below.

Rules:
- Work through each criterion's checklist one item at a time.
- A criterion passes only when every checklist item is clearly satisfied.
- If any item is unclear, ambiguous, or cannot be decided from the evidence \
below, FAIL the criterion. Never pass a criterion you are unsure about.

Evidence from this session's tool results (the only facts the reply may state):
{evidence}

The reply under review:
\"\"\"{output}\"\"\"

Criteria to decide, with their checklists:
{criteria}

Respond with exactly one JSON object and no other text:
{{"verdicts": [{{"criterion_id": "<id>", "passed": true, "reason": "<short \
reason>"}}]}}
One entry per criterion, in the order listed, using the criterion ids exactly \
as given."""


def _checklist_items(text: str) -> list[str]:
    """Split one criterion into the items the judge checks one at a time."""
    items = [part.strip() for part in re.split(r";|,? and ", text)]
    return [item for item in items if item]


def _render_evidence(evidence: Evidence) -> str:
    """The evidence facts the judge may ground claims against."""
    lines = [
        f"- amounts: {sorted(str(a) for a in evidence.amounts) or 'none'}",
        f"- dates: {sorted(d.isoformat() for d in evidence.dates) or 'none'}",
        f"- merchants: {sorted(evidence.merchants) or 'none'}",
        f"- payment statuses: {sorted(s.value for s in evidence.statuses) or 'none'}",
        f"- customer language: {evidence.customer_language}",
        f"- actions confirmed by read-back: {sorted(evidence.read_backs) or 'none'}",
    ]
    return "\n".join(lines)


def build_judge_prompt(output: str, evidence: Evidence, criteria: Sequence[Criterion]) -> str:
    """The versioned judge prompt for one output and its remaining criteria."""
    blocks = []
    for index, criterion in enumerate(criteria, start=1):
        items = "\n".join(f"   - {item}" for item in _checklist_items(criterion.text))
        blocks.append(f"{index}. id: {criterion.id}\n   Criterion: {criterion.text}\n{items}")
    return _JUDGE_PROMPT_TEMPLATE.format(
        evidence=_render_evidence(evidence),
        output=output,
        criteria="\n".join(blocks),
    )


def parse_judge_response(response: str, criteria: Sequence[Criterion]) -> list[CriterionVerdict]:
    """Turn the judge's response into one verdict per criterion, failing closed.

    A criterion the response does not decide fails; a response that cannot be
    read at all fails every criterion. A timeout or transport error never
    reaches this parser: the caller counts it as a failure (spec: Behaviour).
    """
    text = response.strip()
    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    try:
        payload = json.loads(text)
        entries = payload["verdicts"]
        if not isinstance(entries, list):
            raise TypeError("verdicts is not a list")
    except (ValueError, KeyError, TypeError):
        return [
            CriterionVerdict(
                criterion_id=criterion.id,
                passed=False,
                checker=CheckerKind.JUDGE,
                reason="judge response could not be read",
            )
            for criterion in criteria
        ]

    by_id = {}
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("criterion_id"), str):
            by_id[entry["criterion_id"]] = entry

    verdicts = []
    for criterion in criteria:
        entry = by_id.get(criterion.id)
        if entry is None or not isinstance(entry.get("passed"), bool):
            verdicts.append(
                CriterionVerdict(
                    criterion_id=criterion.id,
                    passed=False,
                    checker=CheckerKind.JUDGE,
                    reason="judge returned no clear verdict for this criterion",
                )
            )
            continue
        reason = entry.get("reason")
        verdicts.append(
            CriterionVerdict(
                criterion_id=criterion.id,
                passed=entry["passed"],
                checker=CheckerKind.JUDGE,
                reason=reason if isinstance(reason, str) and reason else "judge gave no reason",
            )
        )
    return verdicts


class Judge(Protocol):
    """Labels every remaining criterion in one batched call (decision 17)."""

    def judge_batch(
        self, output: str, evidence: Evidence, criteria: Sequence[Criterion]
    ) -> list[CriterionVerdict]:
        """One pass/fail verdict with a short reason per criterion."""
        ...


class MockJudge:
    """The test and demo judge: scripted verdicts, records what it was asked.

    ``calls`` keeps the criterion ids of every call, so cascade tests can prove
    criteria handled by code or Laya never reach the judge.
    """

    def __init__(
        self,
        verdicts: dict[str, tuple[bool, str]] | None = None,
        default: tuple[bool, str] = (True, "mock judge: no scripted verdict"),
    ) -> None:
        self.verdicts = dict(verdicts or {})
        self.default = default
        self.calls: list[list[str]] = []

    def judge_batch(
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
                    checker=CheckerKind.JUDGE,
                    reason=reason,
                )
            )
        return results
