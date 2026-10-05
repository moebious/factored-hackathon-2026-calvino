"""Snapshot construction and source-partition checks for T-105."""

from __future__ import annotations

import json
from pathlib import Path

from calvino.data.freshness import RevisionDisposition, build_initial_state, read_source_revisions

FIXTURE_DIR = Path(__file__).parents[2] / "fixtures" / "freshness"


def _initial_state():
    manifest = json.loads((FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))
    revisions = read_source_revisions(FIXTURE_DIR / manifest["initial_revisions"])
    return build_initial_state(revisions, manifest["frozen_members"])


def test_initial_window_boundaries_have_expected_dispositions():
    state = _initial_state()
    statuses = {status.record_id: status.disposition for status in state.initial_statuses}

    assert statuses["arrival-day0"] is RevisionDisposition.ACCEPTED
    assert statuses["arrival-day30"] is RevisionDisposition.ACCEPTED
    assert statuses["arrival-day31"] is RevisionDisposition.QUARANTINED_LATE


def test_partition_hashes_include_scope_kind_and_process_date():
    state = _initial_state()

    expected = {
        "source:mutable:partition:transaction:2025-03-01",
        "source:mutable:partition:interaction:2025-03-01",
        "source:frozen:partition:transaction:2026-02-01",
        "source:frozen:partition:interaction:2025-03-01",
    }

    assert expected <= state.source_hashes.keys()
    assert all(len(state.source_hashes[source_id]) == 64 for source_id in expected)
    for source_id in expected:
        artifact_id = source_id.removeprefix("source:")
        assert artifact_id in state.lineage_by_id
        assert state.lineage_by_id[artifact_id].artifact_kind == "source_partition"
