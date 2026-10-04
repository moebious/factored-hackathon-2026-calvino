"""Leakage rules L1-L5, each passing on a clean split and failing on a crafted
violation. All fixtures are synthetic (TSD-015, T-103)."""

from __future__ import annotations

from datetime import date

from calvino.data.leakage import (
    CandidateInput,
    SeedEntry,
    check_l1_customer_isolation,
    check_l2_time_order,
    check_l3_dataset_text,
    check_l4_generation_isolation,
    check_l5_gold_held_out,
)


def test_l1_passes_when_splits_are_disjoint():
    assignments = {
        "train": {"SYN-C001", "SYN-C002"},
        "calibration": {"SYN-C003"},
        "test": {"SYN-C004"},
        "gold": {"SYN-C005"},
    }
    assert check_l1_customer_isolation(assignments) == []


def test_l1_fails_when_a_customer_is_in_two_splits():
    assignments = {
        "train": {"SYN-C001", "SYN-C002"},
        "calibration": {"SYN-C003"},
        "test": {"SYN-C002"},
        "gold": {"SYN-C005"},
    }
    violations = check_l1_customer_isolation(assignments)
    assert len(violations) == 1
    assert violations[0].rule_id == "L1"
    assert "SYN-C002" in violations[0].detail


def test_l2_passes_when_windows_are_ordered():
    records = [
        ("train", date(2025, 5, 31)),
        ("calibration", date(2025, 12, 31)),
        ("test", date(2026, 3, 1)),
    ]
    assert check_l2_time_order(records) == []


def test_l2_fails_on_future_data_in_training():
    records = [
        ("train", date(2025, 6, 1)),
        ("calibration", date(2026, 1, 1)),
    ]
    violations = check_l2_time_order(records)
    assert [v.rule_id for v in violations] == ["L2", "L2"]


def test_l3_passes_for_team_written_inputs():
    candidates = [CandidateInput("synthetic team-written message", "team-written")]
    assert check_l3_dataset_text(candidates, {"dataset template text"}, {"team-written"}) == []


def test_l3_fails_on_copied_text_and_unlisted_sources():
    candidates = [
        CandidateInput("dataset template text", "team-written"),
        CandidateInput("other synthetic message", "scraped"),
    ]
    violations = check_l3_dataset_text(candidates, {"dataset template text"}, {"team-written"})
    assert len(violations) == 2
    assert all(v.rule_id == "L3" for v in violations)


def test_l4_passes_with_disjoint_seed_sets():
    entries = [
        SeedEntry("SEED-001", "train", "prompt-train-v1"),
        SeedEntry("SEED-002", "test", "prompt-test-v1"),
    ]
    assert check_l4_generation_isolation(entries) == []


def test_l4_fails_when_a_seed_feeds_both_sides():
    entries = [
        SeedEntry("SEED-001", "train", "prompt-train-v1"),
        SeedEntry("SEED-001", "test", "prompt-test-v1"),
    ]
    violations = check_l4_generation_isolation(entries)
    assert len(violations) == 1
    assert violations[0].rule_id == "L4"


def test_l4_fails_when_a_seed_feeds_calibration_and_another_side():
    entries = [
        SeedEntry("SEED-001", "train", "prompt-train-v1"),
        SeedEntry("SEED-001", "calibration", "prompt-cal-v1"),
        SeedEntry("SEED-002", "calibration", "prompt-cal-v1"),
        SeedEntry("SEED-002", "test", "prompt-test-v1"),
    ]
    violations = check_l4_generation_isolation(entries)
    assert [v.rule_id for v in violations] == ["L4", "L4"]
    assert "train and calibration" in violations[0].detail
    assert "calibration and test" in violations[1].detail


def test_l5_passes_when_gold_stays_held_out():
    violations = check_l5_gold_held_out(
        {"SYN-G001"}, {"SEED-G001"}, {"SYN-T001", "SEED-T001"}, {"SYN-C001", "SEED-C001"}
    )
    assert violations == []


def test_l5_fails_when_gold_keys_train_or_calibrate():
    violations = check_l5_gold_held_out(
        {"SYN-G001"}, {"SEED-G001"}, {"SYN-G001", "SEED-T001"}, {"SYN-C001", "SEED-G001"}
    )
    assert [v.rule_id for v in violations] == ["L5", "L5"]
