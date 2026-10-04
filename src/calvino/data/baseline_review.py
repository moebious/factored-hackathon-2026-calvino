"""Combine reconciled aggregate-only baseline and channel slices into safe staging.

The independent baseline and both measured staging directories remain untouched.
This builds a separate review candidate, not a published report.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

from calvino.data.inventory_access import InventoryError

ROOT = Path(__file__).resolve().parents[3]
BASELINE = ROOT / "data" / "baseline-staging"
CHANNEL = ROOT / "data" / "channel-diagnostic"
REVIEW = ROOT / "data" / "baseline-review"
BASELINE_DIGEST = "aad502d22e333512cb5051455674dca6ab1524b2fa10b30bb08d224fb68edeb7"
CHANNEL_DIGEST = "f30407b5e0ad8029a48edab22361f35bbb2de7caf38d4fde80d32b20c40bceb5"
INTERACTION_FIELDS = (
    "population",
    "slice_type",
    "slice_value",
    "metric",
    "value",
    "n_population",
    "n_valid",
    "n_null_excluded",
    "n_invalid_excluded",
    "n_unresolved_excluded",
    "denominator",
    "small_n",
    "label",
)


def _read(path: Path, fields: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames or set(reader.fieldnames) != fields:
                raise InventoryError("aggregate review input has an unexpected schema")
            rows = list(reader)
    except (OSError, csv.Error, UnicodeError):
        raise InventoryError("aggregate review input is unavailable") from None
    if not rows or any(None in row for row in rows):
        raise InventoryError("aggregate review input is empty or malformed")
    return rows


def _report(path: Path, digest: str) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise InventoryError("aggregate provenance is unavailable") from None
    if digest not in text:
        raise InventoryError("aggregate provenance does not match the reviewed manifest")
    return text


def _reconciled(rows: list[dict[str, str]], count: int) -> None:
    if len(rows) != count or any(row["matches"] != "True" for row in rows):
        raise InventoryError("aggregate comparison is incomplete or has mismatches")


def _write(path: Path, rows: list[dict[str, str]] | str) -> None:
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
        if isinstance(rows, str):
            stream.write(rows)
        else:
            writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)


def prepare(
    *,
    baseline: Path = BASELINE,
    channel: Path = CHANNEL,
    review: Path = REVIEW,
    root: Path = ROOT,
    expected_baseline_cells: int = 128,
    expected_channel_cells: int = 108,
) -> dict[str, int]:
    """Prepare reviewed staging only after both measured inputs and checks agree."""
    if (root / "data").resolve() not in review.resolve().parents or review.is_symlink():
        raise InventoryError("review staging must be inside the ignored worktree data directory")
    if review.exists() and (not review.is_dir() or any(review.iterdir())):
        raise InventoryError("review staging is not empty; existing results are preserved")
    if review.exists() and review.stat().st_mode & 0o077:
        raise InventoryError("review staging directory must be private")
    initial = _report(baseline / "README.md", BASELINE_DIGEST)
    followup = _report(channel / "README.md", CHANNEL_DIGEST)
    if "Status: [measured]" not in initial or "mismatches: 0" not in followup:
        raise InventoryError("input aggregates are not reconciled measurements")
    original = _read(baseline / "interactions.csv", set(INTERACTION_FIELDS))
    complaints = _read(baseline / "complaints.csv", set(INTERACTION_FIELDS))
    new_channel = _read(channel / "channels.csv", set(INTERACTION_FIELDS) - {"label"})
    first_check = _read(
        baseline / "reconciliation.csv",
        {
            "population",
            "slice_type",
            "slice_value",
            "metric",
            "previous_value",
            "observed_value",
            "previous_n_valid",
            "observed_n_valid",
            "matches",
        },
    )
    channel_check = _read(
        channel / "reconciliation.csv",
        {"population", "original_channel", "metric", "previous_value", "observed_value", "matches"},
    )
    _reconciled(first_check, expected_baseline_cells)
    _reconciled(channel_check, expected_channel_cells)
    updated = [{**row, "label": "measured"} for row in new_channel]
    merged = [row for row in original if row["slice_type"] != "channel"] + updated
    if len(merged) != len(original):
        raise InventoryError("remeasured channel slices do not cover the original metric cells")
    for population in ("all interactions", "Transaccional"):
        expected = next(
            (
                int(row["n_population"])
                for row in original
                if row["population"] == population
                and row["slice_type"] == "overall"
                and row["metric"] == "fcr"
            ),
            None,
        )
        observed = sum(
            int(row["n_population"])
            for row in updated
            if row["population"] == population and row["metric"] == "fcr"
        )
        if observed != expected or any(
            row["slice_value"] == "(other)" and row["population"] == population for row in updated
        ):
            raise InventoryError("remeasured channel population is incomplete")
    # The original report's 40,321 "unknown categories" were an incomplete
    # allowlist artifact. Inventory found zero missing categories; all
    # non-Transactions complaints are valid non-target categories here.
    summary = (
        "# Reviewed T-104 baseline (staged, not published)\n\n"
        "[measured] Full live four-table baseline, with call-only channel remeasurement. "
        f"Reviewed manifest digests: {BASELINE_DIGEST} (four tables) and "
        f"{CHANNEL_DIGEST} (calls only). Both inputs reconciled: "
        f"{len(first_check)} independent headline cells and {len(channel_check)} "
        "original grouped-channel cells, zero mismatches.\n\n"
        "The first run incorrectly grouped Web Chat under (other); its 22,856 calls "
        "are now reported as Web Chat (7,997 are Transaccional). Its README also "
        "misnamed non-target complaint categories as unknown. The prior full-data "
        "inventory found zero null complaint categories; the 53,515 complaints "
        "outside Transactions are non-target categories, not missing cases.\n\n"
        "One row is one metric in a named population and slice. Shares use non-null "
        "denominators; zero denominators have no value. Resolution days include "
        "Resolved or Closed only. P90 uses linear interpolation. USD claims use "
        "nearest-earlier daily source-to-USD rates; native currencies are never pooled. "
        "Every metric reports its population, valid, excluded and denominator counts. "
        "small_n flags fewer than 30 valid cases. No call is linked to a specific "
        "stuck payment: these remain category-level proxies, not case-level outcomes.\n\n"
        "Inputs: ignored data/baseline-staging/ and data/channel-diagnostic/. "
        "The independent cross-check files are preserved unchanged. "
        "Publication is a separate maintainer decision.\n"
    )
    review.mkdir(parents=True, mode=0o700, exist_ok=True)
    _write(review / "interactions.csv", merged)
    _write(review / "complaints.csv", complaints)
    _write(review / "headline-reconciliation.csv", first_check)
    _write(review / "channel-reconciliation.csv", channel_check)
    _write(review / "README.md", summary)
    return {"interactions": len(merged), "complaints": len(complaints), "channels": len(updated)}
