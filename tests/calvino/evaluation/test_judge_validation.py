"""Tests for the gated judge validation (TSD-013).

The gated modules are tested for their skip behaviour, not their provider
calls (TSD-013 Behaviour): no keys means ``ran=False`` with the blocker
named and no client built, an empty label set means the same, and the
confusion itself is checked with ``MockJudge`` against hand-computed
numbers. No network, no secrets.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from calvino.evaluation.judge_validation import (
    KEYS_BLOCKER,
    NO_LABELS_BLOCKER,
    HandLabel,
    JudgeConfusion,
    JudgeInput,
    keys_blocker,
    load_hand_labels,
    run_judge_validation,
)
from calvino.evaluation.metrics import Rate
from calvino.verifier.evidence import Evidence
from calvino.verifier.judge import MockJudge
from calvino.verifier.rubric import CheckerKind, Criterion, Rubric, Severity

KEYS_ENV = {"CALVINO_JUDGE_API_KEY": "judge-key", "CALVINO_JUDGE_MODEL": "deepseek-chat"}


def rubric() -> Rubric:
    """A three-criterion judge rubric; ref is "test@1"."""
    return Rubric(
        id="test",
        version=1,
        output_type="customer-answer",
        criteria=[
            Criterion(
                id=f"c{n}",
                text=f"criterion {n}",
                checker=CheckerKind.JUDGE,
                severity=Severity.BLOCKING,
            )
            for n in (1, 2, 3)
        ],
    )


def label(
    case_id: str,
    labels: dict[str, str],
    *,
    rubric_version: str = "test@1",
) -> HandLabel:
    return HandLabel(
        case_id=case_id,
        rubric_version=rubric_version,
        labels=tuple(labels.items()),
        labelled_by="maintainer",
    )


def replies(*case_ids: str) -> dict[str, JudgeInput]:
    return {
        case_id: JudgeInput(output="respuesta", evidence=Evidence(customer_language="es"))
        for case_id in case_ids
    }


def write_label_file(folder: Path, name: str, payload: dict) -> Path:
    path = folder / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


VALID_PAYLOAD = {
    "case_id": "ORC-001",
    "rubric_version": "customer-answer@3",
    "labels": {"grounded-in-evidence": "pass", "no-fabrication": "fail"},
    "labelled_by": "maintainer",
}


def test_keys_blocker_reads_the_gate() -> None:
    assert keys_blocker({}) == KEYS_BLOCKER
    assert keys_blocker({"CALVINO_JUDGE_API_KEY": "k"}) == KEYS_BLOCKER
    assert keys_blocker(KEYS_ENV) is None


def test_load_hand_labels_missing_directory_is_empty(tmp_path: Path) -> None:
    assert load_hand_labels(tmp_path / "absent") == ()


def test_load_hand_labels_round_trip(tmp_path: Path) -> None:
    write_label_file(tmp_path, "labels.json", VALID_PAYLOAD)
    loaded = load_hand_labels(tmp_path)
    assert loaded == (
        HandLabel(
            case_id="ORC-001",
            rubric_version="customer-answer@3",
            labels=(("grounded-in-evidence", "pass"), ("no-fabrication", "fail")),
            labelled_by="maintainer",
        ),
    )


@pytest.mark.parametrize(
    "broken",
    [
        {"case_id": "X"},  # missing fields
        {**VALID_PAYLOAD, "extra": 1},  # unknown field
        {**VALID_PAYLOAD, "labels": {}},  # empty labels
        {**VALID_PAYLOAD, "labels": {"c1": "maybe"}},  # bad label value
    ],
)
def test_load_hand_labels_rejects_broken_files(tmp_path: Path, broken: dict) -> None:
    write_label_file(tmp_path, "labels.json", broken)
    with pytest.raises(ValueError):
        load_hand_labels(tmp_path)


def test_missing_keys_skips_with_named_blocker() -> None:
    # judge=None and no keys must return before any client is built.
    confusion = run_judge_validation(replies("A"), [label("A", {"c1": "pass"})], rubric(), env={})
    assert confusion.ran is False
    assert confusion.blocker == KEYS_BLOCKER
    assert confusion.judged == 0
    assert confusion.agreement == Rate(0, 0)
    assert confusion.agreement.value is None


def test_keys_without_labels_skip_with_named_blocker() -> None:
    # Keys present but nothing labelled: still "not run", and still no client.
    confusion = run_judge_validation({}, [], rubric(), env=KEYS_ENV)
    assert confusion.ran is False
    assert confusion.blocker == NO_LABELS_BLOCKER


def test_confusion_is_hand_computed_with_the_mock_judge() -> None:
    # Judge verdicts: c1 pass, c2 pass, c3 fail.
    # A: c1 labelled pass (agree), c2 labelled fail (judge passed it: false pass).
    # B: c3 labelled pass (judge failed it: false fail).
    judge = MockJudge(verdicts={"c1": (True, "ok"), "c2": (True, "ok"), "c3": (False, "no")})
    confusion = run_judge_validation(
        replies("A", "B"),
        [label("A", {"c1": "pass", "c2": "fail"}), label("B", {"c3": "pass"})],
        rubric(),
        judge=judge,
        env={},
    )
    assert confusion == JudgeConfusion(
        ran=True,
        blocker=None,
        judge_model=None,
        agent_model=None,
        rubric_ref="test@1",
        judged=3,
        false_pass_ids=("A/c2",),
        false_fail_ids=("B/c3",),
        agreement=Rate(1, 3),
        missing_reply_ids=(),
        cost_usd=None,
        cost_per_criterion_usd=None,
    )


def test_labelled_case_without_reply_is_listed_not_dropped() -> None:
    judge = MockJudge(verdicts={"c1": (True, "ok")})
    confusion = run_judge_validation(
        replies("A"),
        [label("A", {"c1": "pass"}), label("D", {"c1": "pass"})],
        rubric(),
        judge=judge,
        env={},
    )
    assert confusion.missing_reply_ids == ("D",)
    assert confusion.judged == 1


def test_rubric_version_mismatch_raises() -> None:
    judge = MockJudge()
    with pytest.raises(ValueError, match="different rubric"):
        run_judge_validation(
            replies("A"),
            [label("A", {"c1": "pass"}, rubric_version="test@2")],
            rubric(),
            judge=judge,
            env={},
        )


def test_labelled_criterion_missing_from_rubric_raises() -> None:
    judge = MockJudge()
    with pytest.raises(ValueError, match="does not contain"):
        run_judge_validation(
            replies("A"), [label("A", {"nope": "pass"})], rubric(), judge=judge, env={}
        )


def test_cost_per_criterion_when_metered() -> None:
    judge = MockJudge(verdicts={"c1": (True, "ok"), "c2": (True, "ok"), "c3": (True, "ok")})
    confusion = run_judge_validation(
        replies("A"),
        [label("A", {"c1": "pass", "c2": "pass", "c3": "pass"})],
        rubric(),
        judge=judge,
        env={},
        cost_usd=0.09,
    )
    assert confusion.judged == 3
    assert confusion.cost_usd == 0.09
    assert confusion.cost_per_criterion_usd == pytest.approx(0.03)


def test_model_ids_are_named_from_the_environment() -> None:
    judge = MockJudge(verdicts={"c1": (True, "ok")})
    confusion = run_judge_validation(
        replies("A"),
        [label("A", {"c1": "pass"})],
        rubric(),
        judge=judge,
        env={**KEYS_ENV, "CALVINO_LLM_MODEL": "Qwen3.8-27B"},
    )
    assert confusion.judge_model == "deepseek-chat"
    assert confusion.agent_model == "Qwen3.8-27B"
