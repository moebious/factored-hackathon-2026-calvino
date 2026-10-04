"""Aggregate-only channel diagnostic over the versioned call table.

The manifest step lists call metadata only. The separately approved scan streams
calls without a local raw copy, checks every object version and byte count, and
reconciles the originally grouped channel cells before staging new aggregates.
"""

from __future__ import annotations

import csv
import os
import re
import time
from collections import Counter
from contextlib import closing
from pathlib import Path
from typing import Any

from calvino.data.baseline_metrics import CallSlice
from calvino.data.baseline_source import s3_rows
from calvino.data.inventory_access import InventoryError, SourceManifest, discover
from calvino.data.inventory_report import EXPECTED_ROWS, check_budget

TABLE = "call_center_interactions"
ROOT = Path(__file__).resolve().parents[3]
STAGE = ROOT / "data" / "channel-diagnostic"
BASELINE = ROOT / "data" / "baseline-staging" / "interactions.csv"
SAFE_LABEL = re.compile(r"[A-Za-z][A-Za-z0-9 _/-]{0,31}\Z")
MAX_LABELS = 64
MIN_LABEL_COUNT = 30
EXPECTED_CALLS = EXPECTED_ROWS[TABLE]
# Freeze the first full run's allowlist for reconciliation: that run grouped
# Web Chat under (other), even after the remeasured label joins the main runner.
ORIGINAL_CHANNELS = frozenset({"Phone", "Chat", "Email", "WhatsApp", "App", "Web", "Branch", "IVR"})


def manifest(s3: Any, bucket: str) -> SourceManifest:
    """Discover only the call table; this makes no full-object GET request."""
    return discover(s3, bucket, tables=(TABLE,))


def _old_channel_rows(path: Path) -> dict[tuple[str, str, str], dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            result = {
                (row["population"], row["slice_value"], row["metric"]): row
                for row in csv.DictReader(handle)
                if row["slice_type"] == "channel"
            }
    except (OSError, csv.Error, KeyError):
        raise InventoryError("staged four-table channel comparison is unavailable") from None
    if not result:
        raise InventoryError("staged four-table channel comparison is empty")
    return result


def _prepare(stage: Path, root: Path) -> None:
    data = (root / "data").resolve()
    if data not in stage.resolve().parents or stage.is_symlink():
        raise InventoryError("channel staging must be inside the ignored worktree data directory")
    if stage.exists() and (not stage.is_dir() or any(stage.iterdir())):
        raise InventoryError("channel staging is not empty; existing files are not replaced")
    if stage.exists() and stage.stat().st_mode & 0o077:
        raise InventoryError("channel staging directory must be private")


def _write(stage: Path, name: str, rows: list[dict] | str) -> None:
    fd = os.open(stage / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
        if isinstance(rows, str):
            handle.write(rows)
        elif rows:
            writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)


def _compare(
    original: dict[tuple[str, str, str], dict[str, str]],
    collapsed: dict[tuple[str, str], CallSlice],
) -> list[dict]:
    observed = {
        (population, channel, cell["metric"]): cell
        for (population, channel), measure in collapsed.items()
        for cell in measure.rows()
    }
    if set(original) != set(observed):
        raise InventoryError("channel diagnostic does not cover the original grouped cells")
    comparison = []
    for key, previous in sorted(original.items()):
        current = observed[key]
        try:
            counts_match = (
                int(previous["n_population"]) == current["n_population"]
                and int(previous["n_valid"]) == current["n_valid"]
                and int(previous["n_null_excluded"]) == current["n_null_excluded"]
                and int(previous["n_invalid_excluded"]) == current["n_invalid_excluded"]
            )
            values_match = (
                previous["value"] == "" and current["value"] is None
                if previous["value"] == "" or current["value"] is None
                else abs(float(previous["value"]) - float(current["value"])) < 1e-8
            )
            matches = counts_match and values_match
        except (ValueError, TypeError, KeyError):
            matches = False
        comparison.append(
            {
                "population": key[0],
                "original_channel": key[1],
                "metric": key[2],
                "previous_value": previous["value"],
                "observed_value": current["value"],
                "matches": matches,
            }
        )
    return comparison


def scan(
    s3: Any,
    bucket: str,
    reviewed: SourceManifest,
    *,
    digest: str,
    max_bytes: int,
    stage: Path = STAGE,
    old_path: Path = BASELINE,
    root: Path = ROOT,
) -> dict[str, int | str]:
    """Scan calls once under the approved ceiling; only aggregates reach staging."""
    check_budget(reviewed, digest=digest, max_bytes=max_bytes)
    _prepare(stage, root)
    old = _old_channel_rows(old_path)
    start = time.monotonic()
    seen: set[str] = set()
    counts: Counter[str | None] = Counter()
    exact: dict[tuple[str, str | None], CallSlice] = {}
    collapsed: dict[tuple[str, str], CallSlice] = {}
    bytes_read = [0]
    with closing(
        s3_rows(
            s3,
            bucket,
            reviewed,
            TABLE,
            digest=digest,
            max_bytes=max_bytes,
            transferred=bytes_read,
        )
    ) as records:
        for row in records:
            key = row["interaction_id"]
            if not key or key in seen:
                raise InventoryError("missing or duplicate call primary key")
            seen.add(key)
            channel = row["channel"]
            counts[channel] += 1
            if len(counts) > MAX_LABELS:
                raise InventoryError("too many channel labels for a safe aggregate diagnostic")
            populations = (
                ("all interactions", "Transaccional")
                if row["reason_category"] == "Transaccional"
                else ("all interactions",)
            )
            for population in populations:
                exact.setdefault((population, channel), CallSlice()).add(row)
                grouped = channel if channel in ORIGINAL_CHANNELS else "(other)"
                collapsed.setdefault((population, grouped), CallSlice()).add(row)
    if len(seen) != EXPECTED_CALLS or bytes_read[0] != reviewed.total_bytes:
        raise InventoryError("call count or transferred bytes differ from the reviewed baseline")
    comparison = _compare(old, collapsed)
    mismatches = sum(not row["matches"] for row in comparison)
    safe = {
        name
        for name, n in counts.items()
        if name and SAFE_LABEL.fullmatch(name) and n >= MIN_LABEL_COUNT
    }
    grouped: dict[tuple[str, str], CallSlice] = {}
    # No raw values reach output: unrecognized or very small labels stay in
    # a single explicitly named residual group; every call remains counted.
    for (population, name), measure in exact.items():
        label = name if name in safe else "(other)"
        target = grouped.setdefault((population, label), CallSlice())
        if label == name:
            grouped[(population, label)] = measure
        else:
            # Re-aggregate a small unsafe label using its exact sufficient
            # counts and numeric values, without retaining or writing records.
            target.total += measure.total
            for attr in ("fcr", "escalation", "follow_up"):
                source_share, dest_share = getattr(measure, attr), getattr(target, attr)
                dest_share.valid += source_share.valid
                dest_share.true += source_share.true
                dest_share.null += source_share.null
            for attr in ("duration", "wait"):
                source_num, dest_num = getattr(measure, attr), getattr(target, attr)
                dest_num.valid.extend(source_num.valid)
                dest_num.null += source_num.null
                dest_num.invalid += source_num.invalid
    result = [
        {"population": population, "slice_type": "channel", "slice_value": channel, **cell}
        for (population, channel), measure in sorted(grouped.items())
        for cell in measure.rows()
    ]
    # A changed baseline cannot be silently labelled as the same measurement.
    if mismatches:
        raise InventoryError("channel diagnostic disagrees with the original grouped metrics")
    _prepare(stage, root)
    stage.mkdir(parents=True, mode=0o700, exist_ok=True)
    _write(stage, "channels.csv", result)
    _write(stage, "reconciliation.csv", comparison)
    residual = sum(n for name, n in counts.items() if name not in safe)
    _write(
        stage,
        "README.md",
        "# Staged channel diagnostic\n\n"
        f"Reviewed manifest digest: {reviewed.digest}; call objects: {len(reviewed.objects)}; "
        f"bytes transferred: {bytes_read[0]}; calls: {len(seen)}.\n\n"
        f"Compared grouped channel cells: {len(comparison)}; mismatches: {mismatches}. "
        f"Safe channel labels: {len(safe)}; residual calls: {residual}. "
        f"Elapsed seconds: {time.monotonic() - start:.1f}.\n\n"
        "This diagnostic replaces only the channel slices after maintainer review. "
        "The earlier overall, country, segment and complaint aggregates remain unchanged. "
        "A nonzero residual requires an explicit limitation, not a guessed label.\n",
    )
    return {
        "calls": len(seen),
        "bytes_read": bytes_read[0],
        "channel_labels": len(safe),
        "residual_calls": residual,
        "cells_compared": len(comparison),
        "mismatches": mismatches,
    }
