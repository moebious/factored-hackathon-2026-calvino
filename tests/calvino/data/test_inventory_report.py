"""Synthetic aggregate report and byte-budget gate tests."""

from __future__ import annotations

import io

import pytest

from calvino.data.inventory_access import TABLE_NAMES, InventoryError, SourceManifest, SourceObject
from calvino.data.inventory_report import (
    TYPE_REVIEW_TABLES,
    build_report,
    check_budget,
    review_type_flags,
)


class FakeS3:
    """GetObject without any write methods, returning invented CSV records."""

    def __init__(self) -> None:
        self.reads = 0

    def get_object(self, *, Bucket: str, Key: str, IfMatch: str) -> dict:
        self.reads += 1
        assert IfMatch == "synthetic"
        rows = {
            "branches": b"branch_id\nbranch-a\n",
            "customers": b"customer_id,country\nprivate-id,Argentina\n",
            "products": b"product_id,customer_id,currency\nproduct-a,private-id,USD\n",
            "service_agents": (
                b"agent_id,assigned_branch_id\nagent-a,branch-a\nagent-b,missing-branch\n"
            ),
            "transactions": (
                b"transaction_id,customer_id,transaction_status,currency,response_code,"
                b"transaction_country\nprivate-id,private-id,Pending,USD,,Mexico\n"
            ),
            "call_center_interactions": (
                b"interaction_id,customer_id,reason_category,contact_reason\n"
                b"private-id,private-id,Transaccional,Transaccional\n"
            ),
            "complaints": (
                b"complaint_id,customer_id,claimed_amount,currency,origin_interaction_id\n"
                b"private-id,private-id,10,USD,\n"
            ),
            "daily_exchange_rates": (
                b"date,source_currency,target_currency,exchange_rate\n2026-10-03,USD,USD,1\n"
            ),
        }
        table = Key.removeprefix("data/").removesuffix(".csv")
        return {"Body": io.BytesIO(rows.get(table, b"id,value\nprivate-id,synthetic\n"))}


def _manifest() -> SourceManifest:
    return SourceManifest(
        tuple(
            SourceObject(table, f"data/{table}.csv", 24, "synthetic", None) for table in TABLE_NAMES
        ),
        "reviewed-digest",
    )


def test_byte_limit_and_digest_are_required_before_reading() -> None:
    manifest = _manifest()
    with pytest.raises(InventoryError, match="changed"):
        check_budget(manifest, digest="different", max_bytes=10_000)
    with pytest.raises(InventoryError, match="byte ceiling"):
        check_budget(manifest, digest="reviewed-digest", max_bytes=10)
    check_budget(manifest, digest="reviewed-digest", max_bytes=manifest.total_bytes)
    check_budget(manifest, digest="reviewed-digest", max_bytes=72, tables=TYPE_REVIEW_TABLES)
    with pytest.raises(InventoryError, match="byte ceiling"):
        check_budget(manifest, digest="reviewed-digest", max_bytes=71, tables=TYPE_REVIEW_TABLES)


def test_report_scans_all_thirteen_without_raw_values() -> None:
    s3 = FakeS3()
    report = build_report(s3, "synthetic-bucket", _manifest())
    assert s3.reads == 13
    assert len(report["tables"]) == 13
    assert report["tables"]["customers"]["rows"] == 1
    assert report["tables"]["digital_events"]["contract_coverage"] == "not contract-validated"
    assert report["tables"]["service_agents"]["row_rule_violations"]["SA-BRANCH-ORPHAN"] == 1
    assert report["label"] == "measured"
    assert report["discrepancies"][0]["claim"] == "row_count"
    assert "private-id" not in str(report)
    assert "synthetic-bucket" not in str(report)


def test_targeted_type_review_reads_only_flagged_tables() -> None:
    s3 = FakeS3()
    result = review_type_flags(s3, "synthetic-bucket", _manifest())
    assert s3.reads == 3
    assert set(result["tables"]) == set(TYPE_REVIEW_TABLES)
    assert "private-id" not in str(result)


def test_missing_rule_counter_is_compared_as_zero() -> None:
    class NoBranchAssignments(FakeS3):
        def get_object(self, *, Bucket: str, Key: str, IfMatch: str) -> dict:
            if Key == "data/service_agents.csv":
                return {"Body": io.BytesIO(b"agent_id,assigned_branch_id\nagent-a,\n")}
            return super().get_object(Bucket=Bucket, Key=Key, IfMatch=IfMatch)

    report = build_report(NoBranchAssignments(), "synthetic-bucket", _manifest())
    assert {
        "table": "service_agents",
        "claim": "SA-BRANCH-ORPHAN",
        "previous": 831,
        "observed": 0,
        "explanation": "unresolved",
    } in report["discrepancies"]
