"""Unit tests for offline policy replay and promotion scorecard (TSD-034, T-408)."""

from __future__ import annotations

import json
from pathlib import Path

from calvino.policy import load_policy
from calvino.policy.scorecard import evaluate_policy_replay, render_scorecard_markdown


def test_evaluate_policy_replay_same_policy_invariant() -> None:
    eval_path = Path("reports/eval/T-303-2026-10-05-f7ca45b.json")
    if not eval_path.is_file():
        return

    with eval_path.open("r", encoding="utf-8") as f:
        eval_data = json.load(f)

    p4 = load_policy("policy/v4.yaml")
    scorecard = evaluate_policy_replay(
        eval_results=eval_data,
        baseline_policy=p4,
        candidate_policy=p4,
        baseline_policy_path_str="policy/v4.yaml",
        candidate_policy_path_str="policy/v4.yaml",
    )

    assert scorecard.baseline_replay_pass_rate == 1.0
    assert scorecard.replayable_records_count == 236
    assert scorecard.excluded_records_count == 149
    assert len(scorecard.flips) == 0
    assert scorecard.unsafe_regressions_count == 0
    assert scorecard.recommendation == "PROMOTE"


def test_evaluate_policy_replay_v3_to_v4() -> None:
    eval_path = Path("reports/eval/T-303-2026-10-05-f7ca45b.json")
    if not eval_path.is_file():
        return

    with eval_path.open("r", encoding="utf-8") as f:
        eval_data = json.load(f)

    p3 = load_policy("policy/v3.yaml")
    p4 = load_policy("policy/v4.yaml")

    scorecard = evaluate_policy_replay(
        eval_results=eval_data,
        baseline_policy=p3,
        candidate_policy=p4,
        baseline_policy_path_str="policy/v3.yaml",
        candidate_policy_path_str="policy/v4.yaml",
    )

    assert scorecard.baseline_policy_version == "v3"
    assert scorecard.candidate_policy_version == "v4"
    assert len(scorecard.flips) == 2
    # Check flip case IDs
    flip_case_ids = {f.case_id for f in scorecard.flips}
    assert "ADV-008" in flip_case_ids
    assert "ORC-023" in flip_case_ids
    assert scorecard.recommendation in ("PROMOTE", "NEEDS_REVIEW")


def test_evaluate_policy_replay_v1_to_v4() -> None:
    eval_path = Path("reports/eval/T-303-2026-10-05-f7ca45b.json")
    if not eval_path.is_file():
        return

    with eval_path.open("r", encoding="utf-8") as f:
        eval_data = json.load(f)

    p1 = load_policy("policy/v1.yaml")
    p4 = load_policy("policy/v4.yaml")

    scorecard = evaluate_policy_replay(
        eval_results=eval_data,
        baseline_policy=p1,
        candidate_policy=p4,
        baseline_policy_path_str="policy/v1.yaml",
        candidate_policy_path_str="policy/v4.yaml",
    )

    assert scorecard.baseline_policy_version == "v1"
    assert scorecard.candidate_policy_version == "v4"
    # Transitioning from v1 to v4 contains significant human -> agents/clarify flips
    assert len(scorecard.flips) > 50


def test_render_scorecard_markdown() -> None:
    eval_path = Path("reports/eval/T-303-2026-10-05-f7ca45b.json")
    if not eval_path.is_file():
        return

    with eval_path.open("r", encoding="utf-8") as f:
        eval_data = json.load(f)

    p3 = load_policy("policy/v3.yaml")
    p4 = load_policy("policy/v4.yaml")

    scorecard = evaluate_policy_replay(
        eval_results=eval_data,
        baseline_policy=p3,
        candidate_policy=p4,
        baseline_policy_path_str="policy/v3.yaml",
        candidate_policy_path_str="policy/v4.yaml",
    )

    md = render_scorecard_markdown(scorecard)
    assert "# Calvino policy replay & promotion scorecard" in md
    assert "## Evaluation header" in md
    assert "## Verdict transition matrices" in md
    assert "ADV-008" in md
