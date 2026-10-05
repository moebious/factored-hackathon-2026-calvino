"""Tests for the committed pull-report writer (TSD-019 P2 evidence, T-106).

Synthetic fixtures only: no network, keys, dataset or salt value (the
salt version only, never the secret).
"""

from __future__ import annotations

import json

from calvino.data.message_set import SALT_VERSION, gate_table_hash
from calvino.data.pull_report import pull_report_dict, write_pull_report
from calvino.data.seed_pull import SplitPullReport

GATE = {"MXN": 8500.0, "COP": 2000000.0, "ARS": 175000.0, "USD": 500.0}


def synthetic_report() -> SplitPullReport:
    return SplitPullReport(
        considered={"train": 12},
        usable={"train": 10},
        drawn={"train": 9},
        excluded={"train": 2},
        usable_complaints={"train": 3},
        complaint_tight={"train": False},
        pool_status_mix={"train": {"Pending": 7, "Approved": 3}},
        drawn_status_mix={"train": {"Pending": 6, "Approved": 3}},
        drawn_kinds={"train": {"problem_transaction": 6, "complaint": 3}},
        drawn_variants={"train": {"MX": 3, "CO": 3, "AR": 3}},
        notes=[],
    )


def test_pull_report_names_counts_hashes_and_seeds():
    """The report carries counts, digests, seeds and versions together."""
    body = pull_report_dict(
        synthetic_report(),
        {"transaction:missing-date": 2},
        manifest_digest="digest-1",
        rng_seed=20261005,
        policy_version="v2",
        gate_table_hash=gate_table_hash(GATE),
    )
    assert body["manifest_digest"] == "digest-1"
    assert body["rng_seed"] == 20261005
    assert body["policy_version"] == "v2"
    assert body["salt_version"] == SALT_VERSION
    assert body["gate_table_hash"] == gate_table_hash(GATE)
    assert body["considered"] == {"train": 12}
    assert body["usable"] == {"train": 10}
    assert body["drawn"] == {"train": 9}
    assert body["drawn_kinds"] == {"train": {"problem_transaction": 6, "complaint": 3}}
    assert body["drawn_variants"] == {"train": {"MX": 3, "CO": 3, "AR": 3}}
    assert body["excluded"] == {"train": 2}
    assert body["skipped"] == {"transaction:missing-date": 2}
    assert body["quotas"]["train"]["problem_transaction"] == 450
    assert body["nominal_no_record"]["train"] == 30


def test_write_pull_report_round_trip(tmp_path):
    """The writer commits JSON the tree can hold: no pointers, no secrets."""
    path = write_pull_report(
        tmp_path / "pull-report.json",
        synthetic_report(),
        {},
        manifest_digest="digest-1",
        rng_seed=7,
        policy_version="v2",
        gate_table_hash=gate_table_hash(GATE),
    )
    body = json.loads(path.read_text(encoding="utf-8"))
    assert body["rng_seed"] == 7
    assert "customer_id" not in path.read_text(encoding="utf-8")
