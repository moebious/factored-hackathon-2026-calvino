"""Offline tests for T-105 source lineage, revision handling and frozen safety."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from calvino.data.freshness import (
    ArtifactLineage,
    FreshnessInputError,
    RevisionDisposition,
    SourceRevision,
    StaleArtifactError,
    apply_revision_update,
    build_initial_state,
    check_artifact_freshness,
    load_gate_limits,
    plan_revision_update,
    read_source_revisions,
)
from calvino.evaluation.oracle import ExpectedOutcome

FIXTURE_DIR = Path(__file__).parents[2] / "fixtures" / "freshness"


@pytest.fixture
def freshness_data():
    manifest = json.loads((FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))
    initial_rows = read_source_revisions(FIXTURE_DIR / manifest["initial_revisions"])
    update_rows = read_source_revisions(FIXTURE_DIR / manifest["updates"])
    initial = build_initial_state(initial_rows, manifest["frozen_members"])
    plan = plan_revision_update(
        update_rows,
        initial.lineage_by_id,
        initial.accepted_revisions,
        initial.frozen_members,
        quarantined_initial_revisions=initial.quarantined_initial_revisions,
    )
    return initial, plan


def _render_update(tmp_path: Path, initial, plan) -> tuple[object, dict, dict]:
    out_dir = tmp_path / "freshness-output"
    report = apply_revision_update(
        plan,
        initial,
        out_dir,
    )
    snapshot = json.loads((out_dir / "snapshot.json").read_text(encoding="utf-8"))
    source_hashes = json.loads((out_dir / "source-hashes.json").read_text(encoding="utf-8"))
    return report, snapshot, source_hashes


def test_same_snapshot_produces_byte_identical_outputs(freshness_data, tmp_path):
    initial, plan = freshness_data
    first = tmp_path / "first"
    second = tmp_path / "second"
    apply_revision_update(plan, initial, first)
    apply_revision_update(plan, initial, second)

    first_files = sorted(path.name for path in first.iterdir())
    second_files = sorted(path.name for path in second.iterdir())

    assert first_files == second_files
    assert all((first / name).read_bytes() == (second / name).read_bytes() for name in first_files)
    lineage = json.loads((first / "lineage.json").read_text(encoding="utf-8"))
    assert {row["producer_commit"] for row in lineage.values()} == {"fixture-commit-v1"}


def test_initial_window_boundaries_have_expected_dispositions():
    manifest = json.loads((FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))
    rows = read_source_revisions(FIXTURE_DIR / manifest["initial_revisions"])
    state = build_initial_state(rows, manifest["frozen_members"])
    statuses = {status.record_id: status.disposition for status in state.initial_statuses}

    assert statuses["arrival-day0"] is RevisionDisposition.ACCEPTED
    assert statuses["arrival-day30"] is RevisionDisposition.ACCEPTED
    assert statuses["arrival-day31"] is RevisionDisposition.QUARANTINED_LATE


def test_arrival_before_process_date_is_invalid():
    raw = json.loads(
        next(
            line
            for line in (FIXTURE_DIR / "initial.jsonl").read_text(encoding="utf-8").splitlines()
            if '"record_id":"arrival-day0"' in line
        )
    )
    raw["revision_no"] = 2
    raw["source_file_id"] = "arrival-day0-invalid-r2"
    raw["arrival_date"] = "2024-12-31"
    invalid = SourceRevision.from_mapping(raw)

    assert "arrival_before_process_date" in invalid.validation_errors


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("revision_no", 1.5),
        ("revision_no", True),
        ("record_id", None),
        ("customer_id", None),
        ("source_file_id", ""),
    ],
)
def test_source_parser_rejects_coerced_revision_and_identity_values(field, value):
    raw = json.loads((FIXTURE_DIR / "initial.jsonl").read_text(encoding="utf-8").splitlines()[0])
    raw[field] = value

    with pytest.raises(FreshnessInputError):
        SourceRevision.from_mapping(raw)


def test_lineage_source_hash_mismatch_is_fail_closed(freshness_data):
    initial, _ = freshness_data
    artifact_id = "mutable:seed:txn-amount"
    source_id = "source:mutable:partition:transaction:2025-03-01"
    changed = dict(initial.source_hashes)
    changed[source_id] = "0" * 64

    with pytest.raises(StaleArtifactError, match="source .* changed"):
        check_artifact_freshness(
            artifact_id,
            initial.lineage_by_id,
            changed,
            initial.contract_versions,
        )


def test_contract_version_change_alone_makes_artifact_stale(freshness_data):
    initial, _ = freshness_data
    artifact_id = "mutable:seed:txn-amount"
    changed_contracts = {**initial.contract_versions, "oracle": "changed"}

    with pytest.raises(StaleArtifactError, match="contract oracle changed"):
        check_artifact_freshness(
            artifact_id,
            initial.lineage_by_id,
            initial.source_hashes,
            changed_contracts,
        )


def test_unknown_lineage_parent_fails_closed(freshness_data):
    initial, _ = freshness_data
    parent = ArtifactLineage(
        artifact_id="child",
        artifact_kind="fixture",
        parent_artifact_ids=("missing-parent",),
        source_hashes=(),
        contract_versions=(("source", "freshness-source-v1"),),
    )
    lineages = {**initial.lineage_by_id, "child": parent}

    with pytest.raises(FreshnessInputError, match="unknown parent artifact"):
        check_artifact_freshness(
            "child", lineages, initial.source_hashes, initial.contract_versions
        )


def test_source_hash_reversion_makes_prior_artifact_fresh_again(freshness_data):
    initial, _ = freshness_data
    artifact_id = "mutable:seed:txn-amount"
    source_id = "source:mutable:partition:transaction:2025-03-01"
    original = initial.source_hashes[source_id]
    changed = {**initial.source_hashes, source_id: "1" * 64}

    with pytest.raises(StaleArtifactError):
        check_artifact_freshness(
            artifact_id, initial.lineage_by_id, changed, initial.contract_versions
        )

    reverted = {**changed, source_id: original}
    check_artifact_freshness(
        artifact_id, initial.lineage_by_id, reverted, initial.contract_versions
    )


def test_source_row_reversion_reuses_the_prior_partition_artifacts():
    manifest = json.loads((FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))
    initial_rows = read_source_revisions(FIXTURE_DIR / manifest["initial_revisions"])
    reverted_row = read_source_revisions(FIXTURE_DIR / "reversion.jsonl")[0]
    initial = build_initial_state(initial_rows, manifest["frozen_members"])
    plan = plan_revision_update(
        [reverted_row],
        initial.lineage_by_id,
        initial.accepted_revisions,
        initial.frozen_members,
        quarantined_initial_revisions=initial.quarantined_initial_revisions,
    )
    partition_source_id = "source:mutable:partition:transaction:2025-03-01"

    assert (
        plan.expected_source_hashes[partition_source_id]
        == initial.source_hashes[partition_source_id]
    )
    assert "mutable:partition:transaction:2025-03-01" not in plan.invalidated_artifact_ids
    assert "mutable:seed:txn-amount" not in plan.invalidated_artifact_ids


def test_partition_hash_rebuilds_descendants_with_unchanged_row_values(tmp_path):
    manifest = json.loads((FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))
    initial_rows = read_source_revisions(FIXTURE_DIR / manifest["initial_revisions"])
    updates = read_source_revisions(FIXTURE_DIR / manifest["updates"])
    initial = build_initial_state(initial_rows, manifest["frozen_members"])
    plan = plan_revision_update(
        [row for row in updates if row.record_id == "unused-field"],
        initial.lineage_by_id,
        initial.accepted_revisions,
        initial.frozen_members,
        quarantined_initial_revisions=initial.quarantined_initial_revisions,
    )
    report, snapshot, hashes = _render_update(tmp_path, initial, plan)
    partition_id = "mutable:partition:interaction:2025-03-01"
    source_id = f"source:{partition_id}"
    label_id = "mutable:proxy:unused-field:was_resolved"

    assert hashes[source_id] != initial.source_hashes[source_id]
    assert partition_id in report.invalidated_artifact_ids
    assert label_id in report.rebuilt_artifact_ids
    assert label_id in report.unchanged_proxy_label_ids
    assert snapshot[label_id] == initial.artifact_values[label_id]
    with pytest.raises(StaleArtifactError):
        check_artifact_freshness(
            label_id,
            initial.lineage_by_id,
            hashes,
            initial.contract_versions,
        )


def test_amount_correction_uses_oracle_outcomes_and_reports_exact_changes(freshness_data, tmp_path):
    initial, plan = freshness_data
    report, snapshot, _ = _render_update(tmp_path, initial, plan)
    seed_id = "mutable:seed:txn-amount"
    evidence_id = "mutable:evidence:txn-amount"

    assert initial.artifact_values[seed_id]["amount_band"] == "under_gate"
    assert initial.artifact_values[seed_id]["expected_outcome"] == ExpectedOutcome.ACT_ALLOW.value
    assert snapshot[seed_id]["amount_band"] == "over_gate"
    assert snapshot[seed_id]["expected_outcome"] == ExpectedOutcome.ACT_ASK.value
    assert seed_id in report.changed_seed_fact_ids
    assert evidence_id in report.changed_evidence_ids


def test_proxy_correction_changes_proxy_labels_and_baseline_cell(freshness_data, tmp_path):
    initial, plan = freshness_data
    report, snapshot, _ = _render_update(tmp_path, initial, plan)
    label_id = "mutable:proxy:proxy-correction:was_resolved"
    cell_id = "mutable:baseline:calibration:was_resolved"

    assert initial.artifact_values[label_id]["value"] is True
    assert snapshot[label_id]["value"] is False
    assert initial.artifact_values[cell_id]["numerator"] == 1
    assert snapshot[cell_id]["numerator"] == 1
    assert initial.artifact_values[cell_id]["denominator"] == 1
    assert snapshot[cell_id]["denominator"] == 2
    assert label_id in report.changed_proxy_label_ids
    assert cell_id in report.changed_baseline_cell_ids


def test_complaint_source_correction_rebuilds_sla_proxy_and_baseline(freshness_data, tmp_path):
    initial, plan = freshness_data
    report, snapshot, _ = _render_update(tmp_path, initial, plan)
    label_id = "mutable:proxy:complaint-correction:sla_breached"
    cell_id = "mutable:baseline:calibration:sla_breached"

    assert initial.artifact_values[label_id]["value"] is True
    assert snapshot[label_id]["value"] is False
    assert initial.artifact_values[cell_id]["numerator"] == 1
    assert snapshot[cell_id]["numerator"] == 0
    assert label_id in report.changed_proxy_label_ids
    assert cell_id in report.changed_baseline_cell_ids


def test_customer_correction_moves_train_row_to_calibration(freshness_data, tmp_path):
    initial, plan = freshness_data
    report, snapshot, _ = _render_update(tmp_path, initial, plan)
    moved = "mutable:proxy:move-customer:was_resolved"

    assert initial.artifact_values[moved]["split"] == "train"
    assert snapshot[moved]["split"] == "calibration"
    assert moved in report.changed_proxy_label_ids
    assert "mutable:baseline:train:was_resolved" in report.changed_baseline_cell_ids
    assert "mutable:baseline:calibration:was_resolved" in report.changed_baseline_cell_ids


def test_pilot_date_correction_removes_old_derived_outputs(freshness_data, tmp_path):
    initial, plan = freshness_data
    report, snapshot, _ = _render_update(tmp_path, initial, plan)
    label_id = "mutable:proxy:move-date:was_resolved"

    assert label_id in initial.artifact_values
    assert label_id not in snapshot
    assert label_id in report.changed_proxy_label_ids


def test_train_to_frozen_move_changes_only_non_frozen_partition_hash(freshness_data, tmp_path):
    initial, plan = freshness_data
    report, snapshot, hashes = _render_update(tmp_path, initial, plan)
    mutable_partition_source = "source:mutable:partition:interaction:2025-03-01"
    mutable_partition = "mutable:partition:interaction:2025-03-01"
    frozen_partition_source = "source:frozen:partition:interaction:2025-03-01"

    assert initial.source_hashes[mutable_partition_source] != hashes[mutable_partition_source]
    assert initial.source_hashes[frozen_partition_source] == hashes[frozen_partition_source]
    assert "mutable:proxy:move-into-frozen:was_resolved" not in snapshot
    assert mutable_partition in report.invalidated_artifact_ids
    assert "move-into-frozen" in report.frozen_set_drift_ids


def test_frozen_record_corrected_out_of_test_is_not_added_to_train(freshness_data, tmp_path):
    initial, plan = freshness_data
    report, snapshot, hashes = _render_update(tmp_path, initial, plan)
    original = "frozen:seed:frozen-move-out"

    assert original in initial.artifact_values
    assert snapshot[original] == initial.artifact_values[original]
    assert "mutable:seed:frozen-move-out" not in snapshot
    assert (
        hashes["source:frozen:partition:transaction:2026-02-01"]
        == initial.source_hashes["source:frozen:partition:transaction:2026-02-01"]
    )
    assert "frozen-move-out" in report.frozen_set_drift_ids


def test_day31_frozen_entry_has_both_reasons_and_no_accepted_hash(freshness_data):
    initial, plan = freshness_data
    status = next(
        row
        for row in plan.revision_statuses
        if row.record_id == "late-frozen-entry" and row.revision_no == 1
    )

    assert status.disposition is RevisionDisposition.FROZEN_DRIFT
    assert status.reasons == ("frozen_set_entered", "late_window")
    assert "late-frozen-entry" in plan.pending_correction_ids
    assert "source:mutable:partition:interaction:2025-04-01" not in plan.expected_source_hashes
    assert "row:late-frozen-entry" not in plan.expected_source_hashes


def test_revision_of_initial_day31_quarantine_remains_pending(freshness_data):
    _, plan = freshness_data
    revision = next(
        row
        for row in plan.revision_statuses
        if row.record_id == "late-quarantined" and row.revision_no == 2
    )

    assert revision.disposition is RevisionDisposition.QUARANTINED_LATE
    assert "initial_revision_quarantined" in revision.reasons
    assert "late-quarantined" in plan.pending_correction_ids


def test_duplicate_revision_is_noop_and_conflicting_number_is_quarantined(freshness_data):
    _, plan = freshness_data
    revisions = [row for row in plan.revision_statuses if row.record_id == "txn-amount"]
    duplicate = next(row for row in revisions if "duplicate_noop" in row.reasons)
    conflict = next(row for row in revisions if "revision_content_conflict" in row.reasons)

    assert duplicate.disposition is RevisionDisposition.ACCEPTED
    assert conflict.disposition is RevisionDisposition.QUARANTINED_INVALID_CORRECTION
    assert "txn-amount" in plan.pending_correction_ids


def test_revision_report_retains_observed_file_digest_for_quarantine(freshness_data, tmp_path):
    initial, plan = freshness_data
    report, _, _ = _render_update(tmp_path, initial, plan)
    conflict = next(
        row for row in report.revision_statuses if "revision_content_conflict" in row.reasons
    )
    source_revision = next(
        row
        for row in read_source_revisions(FIXTURE_DIR / "updates.jsonl")
        if row.source_file_id == conflict.source_file_id
    )
    report_json = json.loads(
        (tmp_path / "freshness-output" / "freshness-report.json").read_text(encoding="utf-8")
    )
    lineage = json.loads(
        (tmp_path / "freshness-output" / "lineage.json").read_text(encoding="utf-8")
    )

    assert conflict.source_file_sha256 == source_revision.source_file_sha256
    assert any(
        row["lineage_artifact_id"] == conflict.lineage_artifact_id
        and row["source_file_sha256"] == source_revision.source_file_sha256
        for row in report_json["revision_statuses"]
    )
    assert conflict.lineage_artifact_id in lineage


def test_duplicate_current_and_out_of_order_revision_are_noops():
    manifest = json.loads((FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))
    initial_rows = read_source_revisions(FIXTURE_DIR / manifest["initial_revisions"])
    updates = read_source_revisions(FIXTURE_DIR / manifest["updates"])
    accepted_revision = next(
        row for row in updates if row.record_id == "txn-amount" and row.revision_no == 2
    )
    lower_revision = next(
        row for row in initial_rows if row.record_id == "txn-amount" and row.revision_no == 1
    )
    accepted_snapshot_revision = replace(
        accepted_revision,
        arrival_date=accepted_revision.process_date,
    )
    current_rows = [
        accepted_snapshot_revision if row.record_id == "txn-amount" else row for row in initial_rows
    ]
    current_state = build_initial_state(current_rows, manifest["frozen_members"])

    duplicate_plan = plan_revision_update(
        [accepted_revision],
        current_state.lineage_by_id,
        current_state.accepted_revisions,
        current_state.frozen_members,
        quarantined_initial_revisions=current_state.quarantined_initial_revisions,
    )
    lower_plan = plan_revision_update(
        [lower_revision],
        current_state.lineage_by_id,
        current_state.accepted_revisions,
        current_state.frozen_members,
        quarantined_initial_revisions=current_state.quarantined_initial_revisions,
    )

    assert duplicate_plan.invalidated_artifact_ids == ()
    assert lower_plan.invalidated_artifact_ids == ()
    assert (
        current_state.accepted_revisions["txn-amount"].content_sha256
        == accepted_revision.content_sha256
    )
    assert (
        next(
            status.disposition
            for status in lower_plan.revision_statuses
            if status.record_id == "txn-amount"
        )
        is RevisionDisposition.SUPERSEDED
    )


def test_frozen_suite_sentinel_correction_keeps_frozen_artifact(freshness_data, tmp_path):
    initial, plan = freshness_data
    status = next(row for row in plan.revision_statuses if row.record_id == "frozen-suite-sentinel")
    report, snapshot, hashes = _render_update(tmp_path, initial, plan)
    artifact_id = "frozen:proxy:frozen-suite-sentinel:was_resolved"

    assert status.disposition is RevisionDisposition.FROZEN_DRIFT
    assert "frozen_suite_sentinel" in status.reasons
    assert snapshot[artifact_id] == initial.artifact_values[artifact_id]
    assert (
        hashes["source:frozen:partition:interaction:2025-03-01"]
        == initial.source_hashes["source:frozen:partition:interaction:2025-03-01"]
    )
    assert artifact_id in report.blocked_frozen_artifact_ids


def test_policy_change_blocks_but_does_not_rebuild_frozen_artifacts(freshness_data, tmp_path):
    initial, _ = freshness_data
    policy = yaml.safe_load(
        (Path(__file__).parents[3] / "policy" / "v2.yaml").read_text(encoding="utf-8")
    )
    policy["gate"]["allow_amount_limit"]["ARS"] = 100
    policy_path = tmp_path / "changed-policy.yaml"
    policy_path.write_text(yaml.safe_dump(policy), encoding="utf-8")
    plan = plan_revision_update(
        [],
        initial.lineage_by_id,
        initial.accepted_revisions,
        initial.frozen_members,
        quarantined_initial_revisions=initial.quarantined_initial_revisions,
        policy_path=policy_path,
    )

    report, snapshot, hashes = _render_update(tmp_path, initial, plan)
    frozen_values = {
        artifact_id: value
        for artifact_id, value in initial.artifact_values.items()
        if artifact_id.startswith("frozen:")
    }

    assert all(snapshot[artifact_id] == value for artifact_id, value in frozen_values.items())
    assert "frozen:seed:frozen-move-out" in report.blocked_frozen_artifact_ids
    assert not report.is_current_to_latest_observed
    assert (
        hashes["source:frozen:partition:transaction:2026-02-01"]
        == initial.source_hashes["source:frozen:partition:transaction:2026-02-01"]
    )


def test_gate_digest_ignores_comments_and_unrelated_policy_fields(tmp_path):
    first = tmp_path / "first.yaml"
    second = tmp_path / "second.yaml"
    changed = tmp_path / "changed.yaml"
    first.write_text(
        """gate:
  allow_amount_limit:
    USD: 500
    MXN: 8500
    COP: 2000000
    ARS: 175000
other: first
""",
        encoding="utf-8",
    )
    second.write_text(
        """# a comment does not change the gate table
other: second
gate:
  allow_amount_limit:
    ARS: 175000
    COP: 2000000
    MXN: 8500
    USD: 500
""",
        encoding="utf-8",
    )
    changed.write_text(
        """gate:
  allow_amount_limit:
    USD: 501
    MXN: 8500
    COP: 2000000
    ARS: 175000
""",
        encoding="utf-8",
    )

    _, first_digest = load_gate_limits(first)
    _, second_digest = load_gate_limits(second)
    _, changed_digest = load_gate_limits(changed)

    assert first_digest == second_digest
    assert first_digest != changed_digest


def test_existing_output_directory_is_never_overwritten(freshness_data, tmp_path):
    initial, plan = freshness_data
    output = tmp_path / "existing"
    output.mkdir()
    sentinel = output / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")

    with pytest.raises(FreshnessInputError, match="output_dir must be empty"):
        apply_revision_update(plan, initial, output)

    assert sentinel.read_text(encoding="utf-8") == "keep"
