"""Run the four-table T-104 baseline into ignored, aggregate-only staging.

Live access requires a reviewed digest and byte ceiling; check-access reads metadata
and a one-byte permission probe only. Nothing is uploaded or promoted automatically.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from contextlib import closing
from pathlib import Path

from calvino.data.baseline_metrics import Baseline
from calvino.data.baseline_source import ORDER, local_rows, s3_rows
from calvino.data.inventory_access import (
    InventoryError,
    discover,
    load_credentials,
    probe,
    s3_client,
)
from calvino.data.inventory_report import EXPECTED_ROWS, check_budget

ROOT = Path(__file__).resolve().parents[2]
STAGING = ROOT / "data" / "baseline-staging"
# The preserved independent cross-check stays the comparison target: the
# published reports/baseline/ holds this runner's own schema (n_valid, not n_cases).
REFERENCE = ROOT / "reports" / "baseline-independent"


def _comparison(table: str, rows: list[dict]) -> list[dict]:
    """Compare common headline aggregates, not new segments/channels/FX statistics."""
    with (REFERENCE / f"{table}.csv").open(encoding="utf-8") as source:
        old = {
            (row["population"], row["slice_type"], row["slice_value"], row["metric"]): row
            for row in csv.DictReader(source)
            if row["slice_type"] in {"overall", "country"}
        }
    current = {
        (row["population"], row["slice_type"], row["slice_value"], row["metric"]): row
        for row in rows
    }
    results = []
    for key, previous in sorted(old.items()):
        row = current.get(key)
        try:
            same = (
                row is not None
                and int(previous["n_cases"]) == row["n_valid"]
                and int(previous["n_null_excluded"]) == row["n_null_excluded"]
                and abs(float(previous["value"]) - float(row["value"])) < 1e-8
            )
        except (ValueError, TypeError):
            same = False
        results.append(
            {
                "population": key[0],
                "slice_type": key[1],
                "slice_value": key[2],
                "metric": key[3],
                "previous_value": previous["value"],
                "observed_value": row["value"] if row is not None else None,
                "previous_n_valid": previous["n_cases"],
                "observed_n_valid": row["n_valid"] if row is not None else None,
                "matches": same,
            }
        )
    return results


def _stage(
    stage: Path, calls: list[dict], complaints: list[dict], report: str, diff: list[dict]
) -> None:
    root_data = (ROOT / "data").resolve()
    if root_data not in stage.resolve().parents or stage.is_symlink():
        raise InventoryError("staging must be inside the worktree's ignored data directory")
    if stage.exists():
        if not stage.is_dir() or any(stage.iterdir()):
            raise InventoryError("staging is not empty; existing files will not be replaced")
    else:
        stage.mkdir(parents=True, mode=0o700)
    if stage.stat().st_mode & 0o077:
        raise InventoryError("staging directory must be private")
    for name, rows in (
        ("interactions.csv", calls),
        ("complaints.csv", complaints),
        ("reconciliation.csv", diff),
    ):
        fd = os.open(stage / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            if rows:
                writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
    fd = os.open(stage / "README.md", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(report)


def run(
    source: str,
    *,
    digest: str | None = None,
    max_bytes: int | None = None,
    check_access: bool = False,
    stage: Path = STAGING,
) -> dict:
    """Return only safe counts and status, never row data or private source locations."""
    start = time.monotonic()
    if check_access and source != "live-s3":
        raise InventoryError("check-access requires live-s3")
    if source == "live-s3":
        bucket = load_credentials()
        s3 = s3_client()
        probe(s3, bucket)
        manifest = discover(s3, bucket, tables=ORDER)
        if check_access:
            return manifest.summary()
        if not digest or max_bytes is None:
            raise InventoryError("full S3 scan needs a reviewed digest and byte ceiling")
        check_budget(manifest, digest=digest, max_bytes=max_bytes)
    else:
        directory = Path(source)
        if not directory.is_dir():
            raise InventoryError("local baseline source is not a directory")
        if digest or max_bytes is not None:
            raise InventoryError("S3 manifest guards do not apply to local input")

    baseline = Baseline()
    transferred = [0]
    consumers = {
        "customers": baseline.load_customers,
        "daily_exchange_rates": baseline.load_fx,
        "call_center_interactions": baseline.load_calls,
        "complaints": baseline.load_complaints,
    }
    for table in ORDER:
        records = (
            s3_rows(
                s3,
                bucket,
                manifest,
                table,
                digest=digest,
                max_bytes=max_bytes,
                transferred=transferred,
            )
            if source == "live-s3"
            else local_rows(directory, table)
        )
        with closing(records):
            consumers[table](records)
    discrepancies = {
        table: {"expected": EXPECTED_ROWS[table], "observed": baseline.rows[table]}
        for table in ORDER
        if source == "live-s3" and baseline.rows[table] != EXPECTED_ROWS[table]
    }
    for rule, expected in (
        ("CP-AMOUNT-NO-CURRENCY", 1040),
        ("CP-ORIGIN-NULL", 67095),
        ("CI-REASON-REPEATS", 686296),
    ):
        if source == "live-s3" and baseline.known_defects[rule] != expected:
            discrepancies[rule] = {
                "expected": expected,
                "observed": baseline.known_defects[rule],
            }
    calls = baseline.output("interactions")
    complaints = baseline.output("complaints")
    comparison = _comparison("interactions", calls) + _comparison("complaints", complaints)
    mismatches = sum(not row["matches"] for row in comparison)
    # A local fixture is never evidence for a full-data measured claim.
    label = (
        "measured" if source == "live-s3" and not discrepancies and not mismatches else "candidate"
    )
    for row in calls + complaints:
        row["label"] = label
    provenance = (
        f"Live data/ prefix, reviewed manifest {manifest.digest}, {manifest.total_bytes} bytes."
        if source == "live-s3"
        else "Local fixture or authorized local copy (not a full-data measurement)."
    )
    report = (
        "# Staged T-104 baseline\n\n"
        f"Status: [{label}]. {provenance}\n\n"
        "Category-level proxies only. These results do not identify stuck-payment calls.\n\n"
        "Shares use non-null denominators; amounts use nearest earlier source-to-USD rate. "
        "Percentiles use linear interpolation; small_n means fewer than 30 valid cases. "
        "Unresolved complaints are excluded from resolution-day statistics. "
        "Claimed amounts by original currency are never pooled across currencies.\n\n"
        f"Rows: {dict(baseline.rows)}. "
        f"Date ranges: {baseline.date_range}. "
        f"Known defects: {dict(baseline.known_defects)}. "
        f"Null or unrecognized slice labels: {dict(baseline.unknown)}. "
        f"Non-target complaint categories: {dict(baseline.non_target)}. "
        "Unrecognized call channels are grouped as (other), not identified individually.\n\n"
        f"Prior headline cells compared: {len(comparison)}; mismatches: {mismatches}; "
        f"row-count discrepancies: {discrepancies}.\n\n"
        f"Bytes read from S3: {transferred[0] if source == 'live-s3' else 'not applicable'}. "
        f"Elapsed seconds: {time.monotonic() - start:.1f}. "
        "CSV S3 reads transfer entire object bodies despite column projection.\n"
    )
    _stage(stage, calls, complaints, report, comparison)
    return {
        "status": label,
        "rows": dict(baseline.rows),
        "cells_compared": len(comparison),
        "mismatches": mismatches,
        "row_count_discrepancies": len(discrepancies),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="live-s3 or a local CSV/Parquet directory")
    parser.add_argument("--check-access", action="store_true")
    parser.add_argument("--manifest-digest")
    parser.add_argument("--max-bytes", type=int)
    parser.add_argument("--stage", type=Path, default=STAGING)
    args = parser.parse_args()
    try:
        result = run(
            args.source,
            digest=args.manifest_digest,
            max_bytes=args.max_bytes,
            check_access=args.check_access,
            stage=args.stage,
        )
    except InventoryError as error:
        print(f"baseline failed: {error}", file=sys.stderr)
        sys.exit(1)
    if args.check_access:
        print(f"Read-only four-table manifest: {result}")
    else:
        print(f"Staged aggregate baseline: {result}")
        if result["mismatches"] or result["row_count_discrepancies"]:
            sys.exit(1)


if __name__ == "__main__":
    main()
