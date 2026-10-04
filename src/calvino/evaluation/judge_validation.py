"""Gated judge validation (TSD-013): is the LLM judge's verdict trustworthy?

Runs the judge over the versioned rubric on the captured replies of the
hand-labelled subset (``evaluation/hand_labels/*.json``) and reports the
confusion against the human labels: the **false-pass rate** (the judge
passed what the hand label fails, the dangerous direction, DESIGN 4.4),
the false-fail rate, agreement, and the cost per judged criterion. The
judge must come from another family than the agent (decisions 20, 29);
the report names both model ids.

Gated on ``CALVINO_JUDGE_*``: with no keys the validation returns
``ran=False`` and a blocker string naming them, so the report renders
``not run: <blocker>`` instead of failing. A second blocker names an
empty hand-label set: without human labels there is nothing to validate
against, keys or not. No provider is imported at module level and no
client is built until a run has keys, labels and replies.

Hand labels are reviewed human work: a label whose ``rubric_version``
does not match the rubric being run, or whose criterion the rubric does
not contain, raises rather than being skipped, because validating a judge
against labels made for a different rubric would produce a confident,
meaningless number. A labelled case with no captured reply is listed in
``missing_reply_ids``, never silently dropped.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from calvino.evaluation.metrics import Rate
from calvino.verifier.evidence import Evidence
from calvino.verifier.judge import Judge
from calvino.verifier.rubric import Rubric

# The gate: both variables must be set before a judge client may be built.
JUDGE_GATE_VARS = ("CALVINO_JUDGE_API_KEY", "CALVINO_JUDGE_MODEL")
AGENT_MODEL_VAR = "CALVINO_LLM_MODEL"  # named in the report next to the judge

# Blocker strings; the report renders "not run: <blocker>".
KEYS_BLOCKER = "CALVINO_JUDGE_API_KEY and CALVINO_JUDGE_MODEL absent"
NO_LABELS_BLOCKER = "no hand labels in evaluation/hand_labels/"

# Where the reviewed hand labels live (schema in the TSD-013 data model).
DEFAULT_HAND_LABELS_DIR = Path(__file__).resolve().parents[3] / "evaluation" / "hand_labels"

_LABEL_VALUES = frozenset({"pass", "fail"})
_LABEL_FIELDS = frozenset({"case_id", "rubric_version", "labels", "labelled_by"})


@dataclass(frozen=True)
class HandLabel:
    """One reviewed human labelling of one case's captured reply."""

    case_id: str
    rubric_version: str  # the rubric ref ("id@version") the labels were made against
    labels: tuple[tuple[str, str], ...]  # (criterion_id, "pass" | "fail"), rubric order kept
    labelled_by: str


@dataclass(frozen=True)
class JudgeInput:
    """What the judge needs for one case: the captured reply and its evidence."""

    output: str
    evidence: Evidence


@dataclass(frozen=True)
class JudgeConfusion:
    """The judge-vs-human confusion; ``ran=False`` carries the blocker."""

    ran: bool
    blocker: str | None
    judge_model: str | None  # both ids named, decisions 20 and 29
    agent_model: str | None
    rubric_ref: str
    judged: int  # (case, criterion) pairs the judge decided
    false_pass_ids: tuple[str, ...]  # "CASE/criterion": judge passed a labelled fail
    false_fail_ids: tuple[str, ...]  # "CASE/criterion": judge failed a labelled pass
    agreement: Rate  # agreeing pairs over all judged pairs
    missing_reply_ids: tuple[str, ...]  # labelled cases with no captured reply
    cost_usd: float | None  # None when the run did not meter the judge
    cost_per_criterion_usd: float | None


def keys_blocker(env: Mapping[str, str] | None = None) -> str | None:
    """The keys blocker for this environment; ``None`` when the gate is open."""
    values = os.environ if env is None else env
    missing = [name for name in JUDGE_GATE_VARS if not values.get(name)]
    return KEYS_BLOCKER if missing else None


def load_hand_labels(directory: str | Path = DEFAULT_HAND_LABELS_DIR) -> tuple[HandLabel, ...]:
    """Read every ``*.json`` hand-label file; a missing directory is an empty set.

    The schema is strict: exactly ``case_id``, ``rubric_version``, ``labels``
    and ``labelled_by``; every label value ``pass`` or ``fail``. An invalid
    file raises rather than loading partially: hand labels are ground truth,
    and a silently repaired label would validate the judge against a guess.
    """
    folder = Path(directory)
    if not folder.is_dir():
        return ()
    loaded: list[HandLabel] = []
    for path in sorted(folder.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"{path.name}: a hand-label file must contain one JSON object")
        unknown = set(payload) - _LABEL_FIELDS
        missing = _LABEL_FIELDS - set(payload)
        if unknown or missing:
            raise ValueError(
                f"{path.name}: hand-label fields must be exactly {sorted(_LABEL_FIELDS)}, "
                f"missing {sorted(missing)}, unknown {sorted(unknown)}"
            )
        labels = payload["labels"]
        if not isinstance(labels, dict) or not labels:
            raise ValueError(f"{path.name}: labels must be a non-empty object")
        bad = {criterion for criterion, value in labels.items() if value not in _LABEL_VALUES}
        if bad:
            raise ValueError(
                f"{path.name}: label values must be 'pass' or 'fail', got other values for "
                f"{sorted(bad)}"
            )
        loaded.append(
            HandLabel(
                case_id=str(payload["case_id"]),
                rubric_version=str(payload["rubric_version"]),
                labels=tuple((str(k), str(v)) for k, v in labels.items()),
                labelled_by=str(payload["labelled_by"]),
            )
        )
    return tuple(loaded)


def _not_run(blocker: str, rubric: Rubric) -> JudgeConfusion:
    """The honest empty result the report renders as ``not run: <blocker>``."""
    return JudgeConfusion(
        ran=False,
        blocker=blocker,
        judge_model=None,
        agent_model=None,
        rubric_ref=rubric.ref,
        judged=0,
        false_pass_ids=(),
        false_fail_ids=(),
        agreement=Rate(0, 0),
        missing_reply_ids=(),
        cost_usd=None,
        cost_per_criterion_usd=None,
    )


def run_judge_validation(
    replies: Mapping[str, JudgeInput],
    hand_labels: Sequence[HandLabel],
    rubric: Rubric,
    *,
    judge: Judge | None = None,
    env: Mapping[str, str] | None = None,
    cost_usd: float | None = None,
) -> JudgeConfusion:
    """Confuse the judge's verdicts with the hand labels, or name the blocker.

    ``judge`` is the test seam: an injected judge (``MockJudge``) runs
    without keys and without network. With ``judge=None`` the gate is
    checked first, then the labels, and only a run that passed both builds
    the real ``OpenAiJudge`` from ``CALVINO_JUDGE_*``. ``cost_usd`` is the
    run's metered judge cost; ``None`` reports the cost as not metered
    rather than inventing a number.
    """
    if judge is None:
        blocker = keys_blocker(env)
        if blocker is not None:
            return _not_run(blocker, rubric)
    if not hand_labels:
        return _not_run(NO_LABELS_BLOCKER, rubric)

    values = os.environ if env is None else env
    judge_model = values.get(JUDGE_GATE_VARS[1])
    agent_model = values.get(AGENT_MODEL_VAR)
    if judge is None:
        # Late imports: building the client imports httpx and reads the keys,
        # and neither may happen at module level (TSD-013 interfaces).
        from calvino.llm import assert_distinct_families, judge_client_from_env
        from calvino.verifier.judge import OpenAiJudge

        if agent_model:
            assert_distinct_families(agent_model, str(judge_model))
        judge = OpenAiJudge(judge_client_from_env(env=values), seed=0)
        judge_model = judge_model or None

    criteria_by_id = {criterion.id: criterion for criterion in rubric.criteria}
    false_pass: list[str] = []
    false_fail: list[str] = []
    missing_reply: list[str] = []
    judged = 0
    agree = 0
    for label in hand_labels:
        if label.rubric_version != rubric.ref:
            raise ValueError(
                f"hand labels for {label.case_id} were made against rubric "
                f"{label.rubric_version}, but this run uses {rubric.ref}: validating against "
                "labels for a different rubric would produce a meaningless number"
            )
        unknown = [criterion for criterion, _ in label.labels if criterion not in criteria_by_id]
        if unknown:
            raise ValueError(
                f"hand labels for {label.case_id} name criteria the rubric {rubric.ref} does "
                f"not contain: {sorted(unknown)}"
            )
        captured = replies.get(label.case_id)
        if captured is None:
            missing_reply.append(label.case_id)
            continue
        criteria = [criteria_by_id[criterion] for criterion, _ in label.labels]
        verdicts = {
            v.criterion_id: v.passed
            for v in judge.judge_batch(captured.output, captured.evidence, criteria)
        }
        for criterion, human in label.labels:
            decided = verdicts.get(criterion)
            if decided is None:  # the judge protocol decides every criterion; be safe anyway
                continue
            judged += 1
            pair_id = f"{label.case_id}/{criterion}"
            if decided and human == "fail":
                false_pass.append(pair_id)
            elif not decided and human == "pass":
                false_fail.append(pair_id)
            else:
                agree += 1

    per_criterion = (cost_usd / judged) if (cost_usd is not None and judged) else None
    return JudgeConfusion(
        ran=True,
        blocker=None,
        judge_model=judge_model,
        agent_model=agent_model,
        rubric_ref=rubric.ref,
        judged=judged,
        false_pass_ids=tuple(false_pass),
        false_fail_ids=tuple(false_fail),
        agreement=Rate(agree, judged),
        missing_reply_ids=tuple(missing_reply),
        cost_usd=cost_usd,
        cost_per_criterion_usd=per_criterion,
    )
