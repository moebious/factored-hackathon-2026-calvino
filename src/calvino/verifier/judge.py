"""The LLM judge interface (TSD-004): one batched call labels the remaining criteria.

Everything real lives behind the ``Judge`` protocol: tests and the demo use
``MockJudge``, and ``OpenAiJudge`` at the bottom of this module is the provider-backed
one. It is deliberately not re-exported from the package, and importing the cascade pulls
only ``calvino.llm.contracts`` (the types and the error ids): ``httpx`` arrives when a
client is built, not when this module is read, so a process that only checks rubrics never
opens an HTTP client.

The prompt template is versioned like the rubric and the policy; every logged verdict
carries the rubric and the prompt version it was made with, so verdicts replay.

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

from calvino.llm.contracts import (
    ChatClient,
    ChatRequest,
    Message,
    MessageRole,
    ReasoningEffort,
    Role,
)
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


DEFAULT_JUDGE_REASONING_TOKENS = 512
DEFAULT_JUDGE_TOKENS_PER_CRITERION = 96


class OpenAiJudge:
    """The real judge: one batched call to a provider, behind ``calvino.llm``.

    This is the class TSD-004 left behind its interface. It is deliberately
    thin: the prompt is ``build_judge_prompt``, the parsing is
    ``parse_judge_response`` and the failure handling is the cascade's
    ``_run_tier``, which already turns a timeout, an error or a malformed
    answer into failed criteria. Nothing here re-implements any of that.

    Two decisions worth stating, both about not fighting the cascade:

    - **Retries are the cascade's.** The client can retry 429 and 5xx, and
      the cascade then retries the whole verification once with the failed
      criteria as feedback. Both retrying means up to nine requests against
      a provider that allows ten per minute, on a case that ends with a
      person anyway, so the judge client is expected to be built with
      ``retries=0``. The requests-per-window limiter, not the retry, is what
      protects the allowance.
    - **A short timeout.** The judge only runs on cases the Gate already
      escalated, so a slow judge does not delay a decision, it delays the
      handoff notice the customer is waiting on. Failing fast and honestly
      to a person reads better than hanging (NFR-4).

    ``prompt_version`` and ``last_model`` are exposed rather than logged
    here: the hub writes the ``DecisionRecord`` that carries them, so the
    judge reports what it used and the hub decides where it goes.
    """

    prompt_version = JUDGE_PROMPT_VERSION

    def __init__(
        self,
        client: ChatClient,
        *,
        seed: int | None = None,
        reasoning_tokens: int = DEFAULT_JUDGE_REASONING_TOKENS,
        tokens_per_criterion: int = DEFAULT_JUDGE_TOKENS_PER_CRITERION,
    ) -> None:
        self._client = client
        # A fixed seed makes a repeated run of the same case comparable (T-303); None leaves the
        # choice to the provider.
        self.seed = seed
        self._reasoning_tokens = reasoning_tokens
        self._tokens_per_criterion = tokens_per_criterion
        self.last_model: str | None = None
        self.last_latency_ms: float | None = None

    def token_budget(self, criteria: int) -> int:
        """The completion budget for ``criteria`` verdicts, thinking included.

        Every model we can reach is a reasoning model, and it spends the budget before it answers:
        one word cost 109-116 output tokens on the agent model, and a judge model asked for 24
        tokens returned finish_reason "length" with nothing but thinking in the content. So the
        budget has to cover the thinking as well as the verdicts, or the call comes back truncated
        and the parser fails closed on a judge that never got to judge. Sized from the rubric
        rather than fixed, because a rubric with more criteria needs more room for the JSON.
        """
        return self._reasoning_tokens + self._tokens_per_criterion * criteria

    def judge_batch(
        self, output: str, evidence: Evidence, criteria: Sequence[Criterion]
    ) -> list[CriterionVerdict]:
        """One call deciding every remaining criterion, parsed fail-closed."""
        if not criteria:
            return []
        response = self._client.complete(
            ChatRequest(
                role=Role.JUDGE,
                messages=(
                    Message(
                        role=MessageRole.USER,
                        content=build_judge_prompt(output, evidence, criteria),
                    ),
                ),
                purpose="verifier-judge",
                # A verdict is a decision, not prose: no sampling, and a fixed seed so a repeated
                # run of the same case is comparable (T-303).
                temperature=0.0,
                seed=self.seed,
                max_tokens=self.token_budget(len(criteria)),
                reasoning_effort=ReasoningEffort.LOW,
            )
        )
        self.last_model = response.model
        self.last_latency_ms = response.latency_ms
        return parse_judge_response(response.text, criteria)
