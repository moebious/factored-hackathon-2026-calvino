"""Snapshot materialization and partition/lineage construction for T-105."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from typing import Any

from calvino.data.freshness_models import (
    ORACLE_VERSION,
    SOURCE_CONTRACT_VERSION,
    SPLIT_CONTRACT_VERSION,
    ArtifactLineage,
    CandidateEvidenceRow,
    FixtureBaselineCell,
    FixtureProxyLabelRow,
    FixtureSeedFactRow,
    FreshnessInputError,
    FreshnessState,
    RevisionDisposition,
    RevisionStatus,
    SourceRevision,
    _ArtifactBundle,
    _current_contract_versions,
    _is_late,
    _lineage,
    _revision_lineage,
    _revision_status,
    load_gate_limits,
    sha256_json,
)
from calvino.data.splits import assign_record
from calvino.evaluation.oracle import OracleFacts, oracle_outcome


def _is_frozen(revision: SourceRevision, frozen_members: set[str]) -> bool:
    if revision.record_id in frozen_members or revision.frozen_suite_sentinel:
        return True
    return assign_record(revision.customer_id, revision.event_date) == "test"


def _partition_rows(
    revisions: Sequence[SourceRevision],
) -> dict[tuple[str, str], list[SourceRevision]]:
    grouped: dict[tuple[str, str], list[SourceRevision]] = {}
    for revision in revisions:
        partition = (revision.record_kind, revision.process_date.isoformat())
        grouped.setdefault(partition, []).append(revision)
    for rows in grouped.values():
        rows.sort(key=lambda row: row.record_id)
    return grouped


def _descendants_of(lineage_by_id: Mapping[str, ArtifactLineage], parent_ids: set[str]) -> set[str]:
    """Find all artifacts whose lineage descends from any listed parent."""
    descendants = set(parent_ids)
    changed = True
    while changed:
        changed = False
        for artifact_id, lineage in lineage_by_id.items():
            if artifact_id not in descendants and any(
                parent in descendants for parent in lineage.parent_artifact_ids
            ):
                descendants.add(artifact_id)
                changed = True
    return descendants


def _jsonable(value: Any) -> Any:
    if hasattr(value, "value") and isinstance(value.value, str):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return {key: _jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Decimal):
        return format(value, "f")
    return value


def _build_bundle(
    mutable_revisions: Mapping[str, SourceRevision],
    frozen_revisions: Mapping[str, SourceRevision],
    gate_limits: Mapping[str, Decimal],
    gate_table_digest: str,
) -> _ArtifactBundle:
    contracts = {
        "source": SOURCE_CONTRACT_VERSION,
        "split": SPLIT_CONTRACT_VERSION,
        "oracle": ORACLE_VERSION,
        "policy": "v2",
    }
    lineages: dict[str, ArtifactLineage] = {}
    values: dict[str, Any] = {}
    hashes: dict[str, str] = {
        "policy:v2:gate.allow_amount_limit": gate_table_digest,
    }
    seeds: dict[str, FixtureSeedFactRow] = {}
    proxies: dict[str, FixtureProxyLabelRow] = {}
    cells: dict[str, FixtureBaselineCell] = {}
    evidence: dict[str, CandidateEvidenceRow] = {}

    scopes: dict[str, list[SourceRevision]] = {
        "mutable": list(mutable_revisions.values()),
        "frozen": list(frozen_revisions.values()),
    }
    for revision in (*scopes["mutable"], *scopes["frozen"]):
        revision_lineage = _revision_lineage(revision)
        lineages[revision.lineage_artifact_id] = revision_lineage
        values[revision.lineage_artifact_id] = {
            "record_id": revision.record_id,
            "revision_no": revision.revision_no,
            "content_sha256": revision.content_sha256,
            "source_file_sha256": revision.source_file_sha256,
        }
        hashes.update(dict(revision_lineage.source_hashes))
    partition_for_record: dict[tuple[str, str], str] = {}
    for scope, rows in scopes.items():
        for (partition_kind, process_date), partition_rows in _partition_rows(rows).items():
            partition_id = f"{scope}:partition:{partition_kind}:{process_date}"
            logical_source_id = f"source:{partition_id}"
            digest = sha256_json([row.partition_row() for row in partition_rows])
            hashes[logical_source_id] = digest
            lineage = _lineage(
                partition_id,
                "source_partition",
                parents=tuple(row.lineage_artifact_id for row in partition_rows),
                source_hashes={logical_source_id: digest},
                contract_versions={"source": SOURCE_CONTRACT_VERSION},
            )
            lineages[partition_id] = lineage
            values[partition_id] = {
                "partition_kind": partition_kind,
                "process_date": process_date,
                "record_ids": [row.record_id for row in partition_rows],
                "sha256": digest,
                "scope": scope,
            }
            for row in partition_rows:
                partition_for_record[(scope, row.record_id)] = partition_id

    proxy_rows_by_group: dict[tuple[str, str, str], list[FixtureProxyLabelRow]] = {}
    for scope, rows in scopes.items():
        for revision in sorted(rows, key=lambda item: item.record_id):
            split = (
                "frozen_suite"
                if scope == "frozen"
                else assign_record(revision.customer_id, revision.event_date)
            )
            if split is None:
                continue
            partition_id = partition_for_record[(scope, revision.record_id)]
            source_artifact_ids: list[str] = []
            if revision.record_kind == "transaction":
                amount = Decimal(str(revision.payload["amount"]))
                currency = str(revision.payload["currency"])
                band = "over_gate" if amount > gate_limits[currency] else "under_gate"
                expected = oracle_outcome(
                    OracleFacts(
                        intent=str(revision.payload["intent"]),
                        ambiguous=bool(revision.payload["ambiguous"]),
                        status=str(revision.payload["status"]),
                        owner=bool(revision.payload["owner"]),
                        amount_band=band,
                        fraud_flag=bool(revision.payload["fraud_flag"]),
                        in_scope=bool(revision.payload["in_scope"]),
                    )
                )
                seed_id = f"{scope}:seed:{revision.record_id}"
                seed = FixtureSeedFactRow(
                    seed_id=seed_id,
                    source_record_id=revision.record_id,
                    split=split,
                    amount=format(amount, "f"),
                    currency=currency,
                    amount_band=band,
                    policy_version="v2",
                    expected_outcome=expected,
                    lineage_id=seed_id,
                )
                seed_lineage = _lineage(
                    seed_id,
                    "fixture_seed_fact",
                    parents=(partition_id,),
                    source_hashes={"policy:v2:gate.allow_amount_limit": gate_table_digest},
                    contract_versions={**contracts, "policy_gate_table": gate_table_digest},
                )
                seeds[seed_id] = seed
                lineages[seed_id] = seed_lineage
                values[seed_id] = _jsonable(seed)
                source_artifact_ids.append(seed_id)
            else:
                label_values = {
                    "was_resolved": revision.payload.get("was_resolved"),
                    "was_escalated": revision.payload.get("was_escalated"),
                    "requires_followup": revision.payload.get("requires_followup"),
                    "sla_breached": revision.payload.get("sla_breached"),
                }
                for label_name, value in sorted(label_values.items()):
                    if value is None:
                        continue
                    label_id = f"{scope}:proxy:{revision.record_id}:{label_name}"
                    proxy = FixtureProxyLabelRow(
                        label_id=label_id,
                        source_record_id=revision.record_id,
                        proxy_label=label_name,
                        value=bool(value),
                        split=split,
                        lineage_id=label_id,
                    )
                    proxy_lineage = _lineage(
                        label_id,
                        "fixture_proxy_label",
                        parents=(partition_id,),
                        contract_versions=contracts,
                    )
                    proxies[label_id] = proxy
                    lineages[label_id] = proxy_lineage
                    values[label_id] = _jsonable(proxy)
                    proxy_rows_by_group.setdefault((scope, split, label_name), []).append(proxy)
                    source_artifact_ids.append(label_id)

            if source_artifact_ids:
                evidence_id = f"{scope}:evidence:{revision.record_id}"
                evidence_digest = sha256_json(
                    {
                        "source_record_id": revision.record_id,
                        "artifacts": [
                            values[artifact_id] for artifact_id in sorted(source_artifact_ids)
                        ],
                    }
                )
                evidence_row = CandidateEvidenceRow(
                    evidence_id=evidence_id,
                    source_record_ids=(revision.record_id,),
                    source_artifact_ids=tuple(sorted(source_artifact_ids)),
                    evidence_digest=evidence_digest,
                    lineage_id=evidence_id,
                )
                evidence_lineage = _lineage(
                    evidence_id,
                    "fixture_candidate_evidence",
                    parents=source_artifact_ids,
                    contract_versions=contracts,
                )
                evidence[evidence_id] = evidence_row
                lineages[evidence_id] = evidence_lineage
                values[evidence_id] = _jsonable(evidence_row)

    for (scope, split, label_name), rows in sorted(proxy_rows_by_group.items()):
        cell_id = f"{scope}:baseline:{split}:{label_name}"
        numerator = sum(row.value for row in rows)
        parents = tuple(sorted(row.label_id for row in rows))
        cell = FixtureBaselineCell(
            cell_id=cell_id,
            proxy_label=label_name,
            split=split,
            numerator=numerator,
            denominator=len(rows),
            lineage_id=cell_id,
        )
        cell_lineage = _lineage(
            cell_id,
            "fixture_baseline_cell",
            parents=parents,
            contract_versions=contracts,
        )
        cells[cell_id] = cell
        lineages[cell_id] = cell_lineage
        values[cell_id] = _jsonable(cell)

    return _ArtifactBundle(lineages, values, hashes, seeds, proxies, cells, evidence)


def build_initial_state(
    revisions: Sequence[SourceRevision],
    frozen_members: Sequence[str],
    *,
    policy_path: Path | None = None,
) -> FreshnessState:
    """Build the last accepted synthetic baseline and pin its frozen subset."""
    gate_limits, gate_digest = load_gate_limits(policy_path)
    frozen = set(frozen_members)
    accepted_all: dict[str, SourceRevision] = {}
    quarantined: list[SourceRevision] = []
    statuses: list[RevisionStatus] = []

    for revision in sorted(revisions, key=lambda item: (item.arrival_date, item.record_id)):
        revision_is_frozen = _is_frozen(revision, frozen)
        revision_is_late = _is_late(revision)
        if revision.validation_errors:
            if revision_is_frozen:
                disposition = RevisionDisposition.FROZEN_DRIFT
                reasons = ["frozen_set_entered", "contract_invalid"]
                if revision_is_late:
                    reasons.append("late_window")
            else:
                disposition = RevisionDisposition.QUARANTINED_INVALID_CORRECTION
                reasons = list(revision.validation_errors)
                if revision_is_late:
                    reasons.append("late_window")
            statuses.append(
                _revision_status(
                    revision,
                    disposition,
                    *reasons,
                )
            )
            quarantined.append(revision)
            continue
        if revision_is_frozen and revision_is_late:
            statuses.append(
                _revision_status(
                    revision,
                    RevisionDisposition.FROZEN_DRIFT,
                    "frozen_set_entered",
                    "late_window",
                )
            )
            quarantined.append(revision)
            continue
        if revision_is_late:
            statuses.append(
                _revision_status(revision, RevisionDisposition.QUARANTINED_LATE, "late_window")
            )
            quarantined.append(revision)
            continue
        if revision.record_id in accepted_all:
            raise FreshnessInputError(f"duplicate initial record id {revision.record_id!r}")
        accepted_all[revision.record_id] = revision
        if assign_record(revision.customer_id, revision.event_date) == "test":
            frozen.add(revision.record_id)
        if revision.frozen_suite_sentinel:
            frozen.add(revision.record_id)
        statuses.append(_revision_status(revision, RevisionDisposition.ACCEPTED))

    missing_frozen = frozen - accepted_all.keys()
    if missing_frozen:
        raise FreshnessInputError(
            "frozen fixture members have no accepted source rows: "
            f"{', '.join(sorted(missing_frozen))}"
        )
    frozen_revisions = {
        record_id: revision
        for record_id, revision in accepted_all.items()
        if record_id in frozen or revision.frozen_suite_sentinel
    }
    mutable_revisions = {
        record_id: revision
        for record_id, revision in accepted_all.items()
        if record_id not in frozen_revisions
    }
    bundle = _build_bundle(mutable_revisions, frozen_revisions, gate_limits, gate_digest)
    revision_lineages = {
        revision.lineage_artifact_id: _revision_lineage(revision) for revision in revisions
    }
    lineages = {**bundle.lineages, **revision_lineages}
    values = dict(bundle.values)
    values.update(
        {
            revision.lineage_artifact_id: {
                "record_id": revision.record_id,
                "revision_no": revision.revision_no,
                "content_sha256": revision.content_sha256,
                "source_file_sha256": revision.source_file_sha256,
            }
            for revision in revisions
        }
    )
    contracts = _current_contract_versions(gate_digest)
    return FreshnessState(
        accepted_revisions=accepted_all,
        quarantined_initial_revisions=tuple(quarantined),
        frozen_members=tuple(sorted(frozen)),
        lineage_by_id=lineages,
        revision_lineage_by_id=revision_lineages,
        artifact_values=values,
        source_hashes=bundle.source_hashes,
        contract_versions=contracts,
        gate_limits=gate_limits,
        gate_table_digest=gate_digest,
        initial_statuses=tuple(statuses),
    )
