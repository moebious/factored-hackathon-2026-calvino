"""Revision resolution and fail-closed checks for T-105 update plans."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from calvino.data.freshness import (
    RevisionDisposition,
    StaleArtifactError,
    build_initial_state,
    check_artifact_freshness,
    plan_revision_update,
    read_source_revisions,
)

FIXTURE_DIR = Path(__file__).parents[2] / "fixtures" / "freshness"


def _plan():
    manifest = json.loads((FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))
    initial_rows = read_source_revisions(FIXTURE_DIR / manifest["initial_revisions"])
    updates = read_source_revisions(FIXTURE_DIR / manifest["updates"])
    initial = build_initial_state(initial_rows, manifest["frozen_members"])
    plan = plan_revision_update(
        updates,
        initial.lineage_by_id,
        initial.accepted_revisions,
        initial.frozen_members,
        quarantined_initial_revisions=initial.quarantined_initial_revisions,
    )
    return initial, plan


def test_accepted_correction_plans_only_affected_artifacts():
    _, plan = _plan()

    assert "mutable:seed:txn-amount" in plan.invalidated_artifact_ids
    assert any(
        status.record_id == "txn-amount"
        and status.revision_no == 2
        and status.disposition is RevisionDisposition.ACCEPTED
        for status in plan.revision_statuses
    )


def test_freshness_rejects_changed_source_and_contract_snapshots():
    initial, _ = _plan()
    artifact_id = "mutable:seed:txn-amount"
    changed_sources = {
        **initial.source_hashes,
        "source:mutable:partition:transaction:2025-03-01": "0" * 64,
    }
    with pytest.raises(StaleArtifactError):
        check_artifact_freshness(
            artifact_id,
            initial.lineage_by_id,
            changed_sources,
            initial.contract_versions,
        )

    changed_contracts = {**initial.contract_versions, "oracle": "changed"}
    with pytest.raises(StaleArtifactError):
        check_artifact_freshness(
            artifact_id,
            initial.lineage_by_id,
            initial.source_hashes,
            changed_contracts,
        )
