"""Public T-105 lineage, freshness and revision-update API."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from calvino.data.freshness_models import (
    ALLOWED_COUNTRIES,
    ALLOWED_CURRENCIES,
    PRODUCER_COMMIT,
    REPROCESSING_WINDOW_DAYS,
    SOURCE_CONTRACT_VERSION,
    SPLIT_CONTRACT_VERSION,
    ArtifactLineage,
    CandidateEvidenceRow,
    ExpectedOutcome,
    FixtureBaselineCell,
    FixtureProxyLabelRow,
    FixtureSeedFactRow,
    FreshnessInputError,
    FreshnessReport,
    FreshnessState,
    RevisionDisposition,
    RevisionStatus,
    SourceRevision,
    StaleArtifactError,
    UpdatePlan,
    _ArtifactBundle,
    _current_contract_versions,
    _is_late,
    _revision_lineage,
    _revision_status,
    canonical_json,
    load_gate_limits,
    read_source_revisions,
    sha256_json,
)
from calvino.data.freshness_snapshot import (
    _build_bundle,
    _descendants_of,
    _is_frozen,
    _jsonable,
    build_initial_state,
)
from calvino.data.splits import assign_record

__all__ = [
    "ALLOWED_COUNTRIES",
    "ALLOWED_CURRENCIES",
    "ArtifactLineage",
    "CandidateEvidenceRow",
    "ExpectedOutcome",
    "FixtureBaselineCell",
    "FixtureProxyLabelRow",
    "FixtureSeedFactRow",
    "FreshnessInputError",
    "FreshnessReport",
    "FreshnessState",
    "PRODUCER_COMMIT",
    "REPROCESSING_WINDOW_DAYS",
    "RevisionDisposition",
    "RevisionStatus",
    "SOURCE_CONTRACT_VERSION",
    "SPLIT_CONTRACT_VERSION",
    "SourceRevision",
    "StaleArtifactError",
    "UpdatePlan",
    "apply_revision_update",
    "build_initial_state",
    "canonical_json",
    "check_artifact_freshness",
    "load_gate_limits",
    "plan_revision_update",
    "read_source_revisions",
    "sha256_json",
]


def check_artifact_freshness(
    artifact_id: str,
    lineage_by_id: Mapping[str, ArtifactLineage],
    source_hashes_for_selected_snapshot: Mapping[str, str],
    current_contract_versions: Mapping[str, str],
) -> None:
    """Raise if any source, contract, or ancestor differs from the selected snapshot."""
    visiting: set[str] = set()
    checked: set[str] = set()

    def visit(current_id: str) -> None:
        if current_id in checked:
            return
        if current_id in visiting:
            raise FreshnessInputError(f"artifact lineage cycle at {current_id!r}")
        lineage = lineage_by_id.get(current_id)
        if lineage is None:
            raise FreshnessInputError(f"unknown parent artifact id {current_id!r}")
        visiting.add(current_id)
        for source_id, digest in lineage.source_hashes:
            current_digest = source_hashes_for_selected_snapshot.get(source_id)
            if current_digest is None:
                raise StaleArtifactError(f"{current_id} is stale: source {source_id} is missing")
            if current_digest != digest:
                raise StaleArtifactError(f"{current_id} is stale: source {source_id} changed")
        for contract_id, version in lineage.contract_versions:
            current_version = current_contract_versions.get(contract_id)
            if current_version is None:
                raise StaleArtifactError(
                    f"{current_id} is stale: contract {contract_id} is missing"
                )
            if current_version != version:
                raise StaleArtifactError(f"{current_id} is stale: contract {contract_id} changed")
        for parent_id in lineage.parent_artifact_ids:
            visit(parent_id)
        visiting.remove(current_id)
        checked.add(current_id)

    visit(artifact_id)


def plan_revision_update(
    revisions: Sequence[SourceRevision],
    lineage_by_id: Mapping[str, ArtifactLineage],
    accepted_revisions: Mapping[str, SourceRevision],
    frozen_members: Sequence[str],
    *,
    quarantined_initial_revisions: Sequence[SourceRevision] = (),
    policy_path: Path | None = None,
) -> UpdatePlan:
    """Resolve revisions and plan separate mutable and frozen snapshots."""
    gate_limits, gate_digest = load_gate_limits(policy_path)
    frozen = set(frozen_members)
    current = dict(accepted_revisions)
    highest_seen = dict(accepted_revisions)
    revision_lineage_by_id = {
        artifact_id: lineage
        for artifact_id, lineage in lineage_by_id.items()
        if lineage.artifact_kind == "source_revision"
    }
    quarantined_first_seen = {row.record_id for row in quarantined_initial_revisions}
    pending_ids: set[str] = set(quarantined_first_seen)
    frozen_drift_ids: set[str] = set()
    blocked_ids: set[str] = set()
    statuses: list[RevisionStatus] = []
    for initial in quarantined_initial_revisions:
        reasons: list[str] = []
        if _is_late(initial):
            reasons.append("late_window")
        if initial.validation_errors:
            reasons.append("contract_invalid")
        if _is_frozen(initial, frozen):
            disposition = RevisionDisposition.FROZEN_DRIFT
            reasons.append("frozen_set_entered")
            frozen_drift_ids.add(initial.record_id)
        elif initial.validation_errors:
            disposition = RevisionDisposition.QUARANTINED_INVALID_CORRECTION
            reasons.extend(initial.validation_errors)
        else:
            disposition = RevisionDisposition.QUARANTINED_LATE
        statuses.append(_revision_status(initial, disposition, *reasons))
        revision_lineage_by_id[initial.lineage_artifact_id] = _revision_lineage(initial)
        highest_seen[initial.record_id] = initial

    for revision in sorted(
        enumerate(revisions),
        key=lambda pair: (pair[1].arrival_date, pair[1].revision_no, pair[0]),
    ):
        item = revision[1]
        previous = current.get(item.record_id)
        previous_seen = highest_seen.get(item.record_id)
        previous_frozen = item.record_id in frozen or (
            previous is not None and _is_frozen(previous, frozen)
        )
        candidate_split = assign_record(item.customer_id, item.event_date)
        candidate_frozen = item.frozen_suite_sentinel or candidate_split == "test"
        reasons: list[str] = []
        first_seen_late = previous is None and _is_late(item)
        if first_seen_late:
            reasons.append("late_window")
        if item.validation_errors:
            reasons.append("contract_invalid")

        if previous_seen is not None and item.revision_no < previous_seen.revision_no:
            revision_lineage_by_id[item.lineage_artifact_id] = _revision_lineage(
                item, previous_seen
            )
            statuses.append(
                _revision_status(item, RevisionDisposition.SUPERSEDED, "lower_revision")
            )
            continue
        same_revision_conflict = False
        if previous_seen is not None and item.revision_no == previous_seen.revision_no:
            if item.content_sha256 == previous_seen.content_sha256:
                statuses.append(
                    _revision_status(item, RevisionDisposition.ACCEPTED, "duplicate_noop")
                )
                continue
            reasons.append("revision_content_conflict")
            same_revision_conflict = True
        elif previous_seen is None or item.revision_no > previous_seen.revision_no:
            highest_seen[item.record_id] = item

        frozen_drift = candidate_frozen or previous_frozen
        if frozen_drift:
            if candidate_frozen and not previous_frozen:
                reasons.append("frozen_set_entered")
            elif previous_frozen and not candidate_frozen:
                reasons.append("frozen_set_left")
            else:
                reasons.append("frozen_record_corrected")
            if item.frozen_suite_sentinel or item.record_id in frozen:
                reasons.append("frozen_suite_sentinel")
            if previous is not None and not previous_frozen and candidate_frozen:
                current.pop(item.record_id, None)
            if "contract_invalid" in reasons or "revision_content_conflict" in reasons:
                pending_ids.add(item.record_id)
            if first_seen_late:
                quarantined_first_seen.add(item.record_id)
                pending_ids.add(item.record_id)
            frozen_drift_ids.add(item.record_id)
            revision_lineage_by_id[item.lineage_artifact_id] = _revision_lineage(item, previous)
            if previous_frozen and previous is not None:
                old_revision_id = previous.lineage_artifact_id
                for artifact_id in _descendants_of(lineage_by_id, {old_revision_id}):
                    lineage = lineage_by_id.get(artifact_id)
                    if lineage is not None and lineage.artifact_kind != "source_revision":
                        blocked_ids.add(artifact_id)
            statuses.append(_revision_status(item, RevisionDisposition.FROZEN_DRIFT, *reasons))
            continue

        if item.record_id in frozen_drift_ids:
            pending_ids.add(item.record_id)
            revision_lineage_by_id[item.lineage_artifact_id] = _revision_lineage(
                item, previous_seen
            )
            statuses.append(
                _revision_status(
                    item,
                    RevisionDisposition.FROZEN_DRIFT,
                    "unresolved_frozen_drift",
                )
            )
            continue

        if item.validation_errors or same_revision_conflict:
            pending_ids.add(item.record_id)
            revision_lineage_by_id[item.lineage_artifact_id] = _revision_lineage(item, previous)
            statuses.append(
                _revision_status(
                    item,
                    RevisionDisposition.QUARANTINED_INVALID_CORRECTION,
                    *reasons,
                )
            )
            if previous is None:
                quarantined_first_seen.add(item.record_id)
            continue

        if previous is None and item.record_id in quarantined_first_seen:
            pending_ids.add(item.record_id)
            revision_lineage_by_id[item.lineage_artifact_id] = _revision_lineage(item, previous)
            statuses.append(
                _revision_status(
                    item,
                    RevisionDisposition.QUARANTINED_LATE,
                    "initial_revision_quarantined",
                )
            )
            continue

        if first_seen_late:
            pending_ids.add(item.record_id)
            quarantined_first_seen.add(item.record_id)
            revision_lineage_by_id[item.lineage_artifact_id] = _revision_lineage(item, previous)
            statuses.append(
                _revision_status(item, RevisionDisposition.QUARANTINED_LATE, "late_window")
            )
            continue

        current[item.record_id] = item
        revision_lineage_by_id[item.lineage_artifact_id] = _revision_lineage(item, previous)
        statuses.append(_revision_status(item, RevisionDisposition.ACCEPTED, *reasons))

    mutable_revisions = {
        record_id: row for record_id, row in current.items() if not _is_frozen(row, frozen)
    }
    frozen_revisions = {
        record_id: row for record_id, row in current.items() if _is_frozen(row, frozen)
    }
    final_bundle = _build_bundle(
        mutable_revisions,
        frozen_revisions,
        gate_limits,
        gate_digest,
    )
    current_contracts = _current_contract_versions(gate_digest)
    prior_mutable, prior_frozen = _split_snapshot(accepted_revisions, frozen)
    prior_bundle = _build_bundle(prior_mutable, prior_frozen, gate_limits, gate_digest)
    already_stale: set[str] = set()
    for artifact_id in lineage_by_id:
        try:
            check_artifact_freshness(
                artifact_id,
                lineage_by_id,
                prior_bundle.source_hashes,
                current_contracts,
            )
        except StaleArtifactError:
            already_stale.add(artifact_id)
    invalidated: set[str] = set()
    for artifact_id in lineage_by_id:
        try:
            check_artifact_freshness(
                artifact_id, lineage_by_id, final_bundle.source_hashes, current_contracts
            )
        except StaleArtifactError:
            if artifact_id not in already_stale:
                invalidated.add(artifact_id)

    return UpdatePlan(
        accepted_revisions=current,
        frozen_revisions=frozen_revisions,
        frozen_members=tuple(sorted(frozen)),
        revision_statuses=tuple(
            sorted(statuses, key=lambda status: (status.record_id, status.revision_no))
        ),
        revision_lineage_by_id=revision_lineage_by_id,
        quarantined_initial_revisions=tuple(quarantined_initial_revisions),
        pending_correction_ids=tuple(sorted(pending_ids)),
        frozen_set_drift_ids=tuple(sorted(frozen_drift_ids)),
        blocked_frozen_artifact_ids=tuple(sorted(blocked_ids)),
        invalidated_artifact_ids=tuple(sorted(invalidated)),
        expected_source_hashes=final_bundle.source_hashes,
        current_contract_versions=current_contracts,
        gate_limits=gate_limits,
        gate_table_digest=gate_digest,
    )


def _different_ids(
    before: Mapping[str, Any], after: Mapping[str, Any]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    changed = tuple(
        sorted(
            artifact_id
            for artifact_id in before.keys() | after.keys()
            if before.get(artifact_id) != after.get(artifact_id)
        )
    )
    unchanged = tuple(
        sorted(
            artifact_id
            for artifact_id in before.keys() & after.keys()
            if before.get(artifact_id) == after.get(artifact_id)
        )
    )
    return changed, unchanged


def _all_values(bundle: _ArtifactBundle) -> dict[str, Any]:
    return {key: _jsonable(value) for key, value in bundle.values.items()}


def _split_snapshot(
    rows: Mapping[str, SourceRevision], frozen_members: set[str]
) -> tuple[dict[str, SourceRevision], dict[str, SourceRevision]]:
    frozen = {
        record_id: row
        for record_id, row in rows.items()
        if record_id in frozen_members
        or row.frozen_suite_sentinel
        or assign_record(row.customer_id, row.event_date) == "test"
    }
    mutable = {record_id: row for record_id, row in rows.items() if record_id not in frozen}
    return mutable, frozen


def _write_json(path: Path, data: Any) -> None:
    path.write_text(canonical_json(data) + "\n", encoding="utf-8")


def apply_revision_update(
    plan: UpdatePlan,
    initial_state: FreshnessState,
    output_dir: Path,
) -> FreshnessReport:
    """Rebuild accepted non-frozen fixture outputs and write a deterministic report."""
    frozen_members = set(plan.frozen_members)
    source_rows = initial_state.accepted_revisions
    lineage_by_id = initial_state.lineage_by_id
    old_mutable, old_frozen = _split_snapshot(source_rows, frozen_members)
    old_bundle = _build_bundle(
        old_mutable,
        old_frozen,
        initial_state.gate_limits,
        initial_state.gate_table_digest,
    )
    new_frozen = dict(plan.frozen_revisions)
    new_mutable = {
        record_id: row
        for record_id, row in plan.accepted_revisions.items()
        if record_id not in new_frozen
    }
    new_bundle = _build_bundle(
        new_mutable,
        new_frozen,
        plan.gate_limits,
        plan.gate_table_digest,
    )

    resolved_lineages: dict[str, ArtifactLineage] = {}
    resolved_values: dict[str, Any] = {}
    invalidated = set(plan.invalidated_artifact_ids)
    blocked_frozen = set(plan.blocked_frozen_artifact_ids)
    rebuilt: set[str] = set()
    for artifact_id, new_lineage in new_bundle.lineages.items():
        old_lineage = lineage_by_id.get(artifact_id)
        if old_lineage is None:
            rebuilt.add(artifact_id)
            resolved_lineages[artifact_id] = new_lineage
            resolved_values[artifact_id] = new_bundle.values[artifact_id]
            continue
        is_frozen_artifact = artifact_id.startswith("frozen:")
        if is_frozen_artifact:
            resolved_lineages[artifact_id] = old_lineage
            resolved_values[artifact_id] = initial_state.artifact_values[artifact_id]
            try:
                check_artifact_freshness(
                    artifact_id,
                    lineage_by_id,
                    new_bundle.source_hashes,
                    plan.current_contract_versions,
                )
            except StaleArtifactError:
                blocked_frozen.add(artifact_id)
            continue
        try:
            check_artifact_freshness(
                artifact_id,
                lineage_by_id,
                new_bundle.source_hashes,
                plan.current_contract_versions,
            )
        except StaleArtifactError:
            invalidated.add(artifact_id)
            rebuilt.add(artifact_id)
            resolved_lineages[artifact_id] = new_lineage
            resolved_values[artifact_id] = new_bundle.values[artifact_id]
            continue

        resolved_lineages[artifact_id] = old_lineage
        resolved_values[artifact_id] = old_bundle.values.get(
            artifact_id, new_bundle.values[artifact_id]
        )

    all_new_lineage = {**resolved_lineages, **plan.revision_lineage_by_id}
    resolved_bundle = _ArtifactBundle(
        lineages=resolved_lineages,
        values=resolved_values,
        source_hashes=new_bundle.source_hashes,
        seeds=new_bundle.seeds,
        proxy_labels=new_bundle.proxy_labels,
        baseline_cells=new_bundle.baseline_cells,
        evidence=new_bundle.evidence,
    )
    for artifact_id, old_lineage in lineage_by_id.items():
        if artifact_id in all_new_lineage or old_lineage.artifact_kind == "source_revision":
            continue
        try:
            check_artifact_freshness(
                artifact_id,
                lineage_by_id,
                new_bundle.source_hashes,
                plan.current_contract_versions,
            )
        except StaleArtifactError:
            invalidated.add(artifact_id)

    seed_changed, seed_unchanged = _different_ids(old_bundle.seeds, resolved_bundle.seeds)
    proxy_changed, proxy_unchanged = _different_ids(
        old_bundle.proxy_labels, resolved_bundle.proxy_labels
    )
    cell_changed, cell_unchanged = _different_ids(
        old_bundle.baseline_cells, resolved_bundle.baseline_cells
    )
    evidence_changed, evidence_unchanged = _different_ids(
        old_bundle.evidence, resolved_bundle.evidence
    )
    statuses = plan.revision_statuses
    current = (
        not plan.pending_correction_ids and not plan.frozen_set_drift_ids and not blocked_frozen
    )
    report = FreshnessReport(
        revision_statuses=statuses,
        pending_correction_ids=plan.pending_correction_ids,
        rebuilt_artifact_ids=tuple(sorted(rebuilt)),
        invalidated_artifact_ids=tuple(sorted(invalidated)),
        changed_seed_fact_ids=seed_changed,
        unchanged_seed_fact_ids=seed_unchanged,
        changed_proxy_label_ids=proxy_changed,
        unchanged_proxy_label_ids=proxy_unchanged,
        changed_baseline_cell_ids=cell_changed,
        unchanged_baseline_cell_ids=cell_unchanged,
        changed_evidence_ids=evidence_changed,
        unchanged_evidence_ids=evidence_unchanged,
        blocked_frozen_artifact_ids=tuple(sorted(blocked_frozen)),
        frozen_set_drift_ids=plan.frozen_set_drift_ids,
        is_current_to_latest_observed=current,
    )

    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FreshnessInputError("output_dir must be empty; existing files are never removed")
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "freshness-report.json", report.to_dict())
    _write_json(output_dir / "snapshot.json", _all_values(resolved_bundle))
    _write_json(
        output_dir / "lineage.json",
        {
            artifact_id: _jsonable(lineage)
            for artifact_id, lineage in sorted(all_new_lineage.items())
        },
    )
    _write_json(output_dir / "source-hashes.json", dict(resolved_bundle.source_hashes))
    return report
