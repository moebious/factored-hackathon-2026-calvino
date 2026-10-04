"""Aggregate-only full-data report and comparisons with the recorded dataset summary."""

from __future__ import annotations

from typing import Any

from botocore.exceptions import BotoCoreError, ClientError

from calvino.data.contracts import TABLES
from calvino.data.inventory_access import InventoryError, SourceManifest, _safe_error
from calvino.data.inventory_scan import scan_table

# Independently recomputed rows are compared with these earlier measured counts.
EXPECTED_ROWS = {
    "customers": 150_000,
    "products": 400_000,
    "branches": 350,
    "service_agents": 1_200,
    "marketing_campaigns": 200,
    "transactions": 4_425_008,
    "call_center_interactions": 686_296,
    "call_transcripts": 171_321,
    "satisfaction_surveys": 212_759,
    "digital_events": 15_620_994,
    "complaints": 67_095,
    "campaign_sends": 1_746_801,
    "daily_exchange_rates": 13_164,
}
EXPECTED_RULES = {
    "TX-RESPONSE-CODE-NULL": 221_033,
    "TX-COUNTRY-MEXICO": 40_515,
    "CP-AMOUNT-NO-CURRENCY": 1_040,
    "CP-ORIGIN-NULL": 67_095,
    "CI-REASON-REPEATS": 686_296,
    "SA-BRANCH-ORPHAN": 831,
}
TYPE_REVIEW_TABLES = ("transactions", "complaints", "campaign_sends")


def build_report(s3: Any, bucket: str, manifest: SourceManifest) -> dict[str, object]:
    """Scan every object once, returning only aggregate statistics."""
    tables: dict[str, dict[str, object]] = {}
    discrepancies: list[dict[str, object]] = []
    branch_ids: set[str] = set()
    for name, old_count in EXPECTED_ROWS.items():
        objects = [obj for obj in manifest.objects if obj.table == name]

        def open_object(obj: Any) -> Any:
            try:
                request = {"Bucket": bucket, "Key": obj.key}
                if obj.etag:
                    request["IfMatch"] = obj.etag
                return s3.get_object(**request)["Body"]
            except (ClientError, BotoCoreError) as error:
                raise _safe_error(error) from None

        def count_branch_link(table: Any, row: dict[str, str | None]) -> None:
            if table.name == "branches" and row.get("branch_id"):
                branch_ids.add(row["branch_id"])
            elif table.name == "service_agents" and row.get("assigned_branch_id"):
                table.row_rules["SA-BRANCH-ORPHAN"] += row["assigned_branch_id"] not in branch_ids

        counts = scan_table(name, objects, open_object, on_row=count_branch_link).result()
        counts["contract_coverage"] = (
            "row-local rules and agent-branch link recounted; other PK/FK checks not re-audited"
            if name in TABLES
            else "not contract-validated"
        )
        tables[name] = counts
        if counts["rows"] != old_count:
            discrepancies.append(
                {
                    "table": name,
                    "claim": "row_count",
                    "previous": old_count,
                    "observed": counts["rows"],
                    "explanation": "unresolved",
                }
            )
        for rule, previous in EXPECTED_RULES.items():
            if not rule.startswith(("TX-", "CP-", "CI-", "SA-")):
                continue
            expected_table = {
                "TX-": "transactions",
                "CP-": "complaints",
                "CI-": "call_center_interactions",
                "SA-": "service_agents",
            }[rule[:3]]
            observed = counts["row_rule_violations"].get(rule, 0)
            if name == expected_table and observed != previous:
                discrepancies.append(
                    {
                        "table": name,
                        "claim": rule,
                        "previous": previous,
                        "observed": observed,
                        "explanation": "unresolved",
                    }
                )
    if sum(int(table["rows"]) for table in tables.values()) != sum(EXPECTED_ROWS.values()):
        # Per-table differences already name the cause; the total is a separate headline.
        discrepancies.append(
            {
                "table": "all",
                "claim": "total_rows",
                "previous": sum(EXPECTED_ROWS.values()),
                "observed": sum(int(table["rows"]) for table in tables.values()),
                "explanation": "unresolved",
            }
        )
    return {
        "source": "organizer live data/ prefix",
        "label": "measured",
        "manifest": manifest.summary(),
        "tables": tables,
        "discrepancies": discrepancies,
        "limitations": [
            "Five tables have no TSD-007 contract.",
            "Row-local checks and the agent-branch link are recounted; other PK/FK checks need "
            "a separate full audit.",
            "Inventory counts do not link a call to a transaction or select a workflow.",
        ],
    }


def check_budget(
    manifest: SourceManifest,
    *,
    digest: str,
    max_bytes: int,
    tables: tuple[str, ...] | None = None,
) -> None:
    """A changed object set or an exceeded byte ceiling stops before any object is read."""
    if manifest.digest != digest:
        raise InventoryError("source manifest changed; review a new manifest before scanning")
    selected_bytes = sum(
        obj.size for obj in manifest.objects if tables is None or obj.table in tables
    )
    if max_bytes < 0 or selected_bytes > max_bytes:
        raise InventoryError("source exceeds the reviewed byte ceiling")


def review_type_flags(s3: Any, bucket: str, manifest: SourceManifest) -> dict[str, object]:
    """Re-read only the three flagged tables with the corrected type-family heuristic."""
    results: dict[str, object] = {}
    for name in TYPE_REVIEW_TABLES:
        objects = [obj for obj in manifest.objects if obj.table == name]

        def open_object(obj: Any) -> Any:
            try:
                return s3.get_object(Bucket=bucket, Key=obj.key, IfMatch=obj.etag)["Body"]
            except (ClientError, BotoCoreError) as error:
                raise _safe_error(error) from None

        table = scan_table(name, objects, open_object).result()
        results[name] = {
            "rows": table["rows"],
            "files": table["files"],
            "schema_drift": table["schema_drift"],
            "mixed_value_types": {
                column: counts["types"]
                for column, counts in table["columns"].items()
                if len(counts["types"]) > 1
            },
        }
    return {
        "label": "targeted type-heuristic diagnostic, not a fresh 13-table audit",
        "tables": results,
    }
