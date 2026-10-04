"""Synthetic review assembly tests: no dataset, S3, or published report writes."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from calvino.data.baseline_review import (
    BASELINE_DIGEST,
    CHANNEL_DIGEST,
    INTERACTION_FIELDS,
    prepare,
)
from calvino.data.inventory_access import InventoryError


def _csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def _metric(population: str, kind: str, channel: str) -> dict:
    return {
        **dict.fromkeys(INTERACTION_FIELDS, ""),
        "population": population,
        "slice_type": kind,
        "slice_value": channel,
        "metric": "fcr",
        "value": "0.5",
        "n_population": "2",
        "n_valid": "2",
        "n_null_excluded": "0",
        "n_invalid_excluded": "0",
        "n_unresolved_excluded": "0",
        "denominator": "2",
        "small_n": "True",
        "label": "measured",
    }


def _inputs(root: Path) -> tuple[Path, Path, Path]:
    baseline = root / "data" / "baseline-staging"
    channel = root / "data" / "channel-diagnostic"
    review = root / "data" / "baseline-review"
    baseline.mkdir(parents=True)
    channel.mkdir()
    (baseline / "README.md").write_text(f"Status: [measured]. {BASELINE_DIGEST}")
    (channel / "README.md").write_text(f"{CHANNEL_DIGEST}; mismatches: 0")
    old = [
        _metric(population, kind, label)
        for population in ("all interactions", "Transaccional")
        for kind, label in (("overall", "all"), ("channel", "(other)"))
    ]
    _csv(baseline / "interactions.csv", old)
    _csv(baseline / "complaints.csv", [_metric("all complaints", "overall", "all")])
    _csv(
        channel / "channels.csv",
        [
            {key: val for key, val in _metric(pop, "channel", "Web Chat").items() if key != "label"}
            for pop in ("all interactions", "Transaccional")
        ],
    )
    _csv(
        baseline / "reconciliation.csv",
        [
            {
                "population": "all interactions",
                "slice_type": "overall",
                "slice_value": "all",
                "metric": "fcr",
                "previous_value": "0.5",
                "observed_value": "0.5",
                "previous_n_valid": "2",
                "observed_n_valid": "2",
                "matches": "True",
            }
        ],
    )
    _csv(
        channel / "reconciliation.csv",
        [
            {
                "population": "all interactions",
                "original_channel": "(other)",
                "metric": "fcr",
                "previous_value": "0.5",
                "observed_value": "0.5",
                "matches": "True",
            }
        ],
    )
    return baseline, channel, review


def test_review_merges_only_channel_slices_and_preserves_inputs(tmp_path: Path) -> None:
    baseline, channel, review = _inputs(tmp_path)
    result = prepare(
        baseline=baseline,
        channel=channel,
        review=review,
        root=tmp_path,
        expected_baseline_cells=1,
        expected_channel_cells=1,
    )
    assert result == {"interactions": 4, "complaints": 1, "channels": 2}
    with (review / "interactions.csv").open() as output:
        rows = list(csv.DictReader(output))
    assert {r["slice_value"] for r in rows if r["slice_type"] == "channel"} == {"Web Chat"}
    assert {r["slice_value"] for r in rows if r["slice_type"] == "overall"} == {"all"}
    assert "not published" in (review / "README.md").read_text()
    assert "(other)" in (baseline / "interactions.csv").read_text()
    assert (channel / "channels.csv").exists()
    with pytest.raises(InventoryError, match="not empty"):
        prepare(
            baseline=baseline,
            channel=channel,
            review=review,
            root=tmp_path,
            expected_baseline_cells=1,
            expected_channel_cells=1,
        )


def test_review_refuses_mismatch_and_external_path(tmp_path: Path) -> None:
    baseline, channel, review = _inputs(tmp_path)
    with pytest.raises(InventoryError, match="inside"):
        prepare(
            baseline=baseline,
            channel=channel,
            review=tmp_path / "outside",
            root=tmp_path,
            expected_baseline_cells=1,
            expected_channel_cells=1,
        )
    comparison = channel / "reconciliation.csv"
    comparison.write_text(comparison.read_text().replace("True", "False"))
    with pytest.raises(InventoryError, match="mismatches"):
        prepare(
            baseline=baseline,
            channel=channel,
            review=review,
            root=tmp_path,
            expected_baseline_cells=1,
            expected_channel_cells=1,
        )
    assert not review.exists()
