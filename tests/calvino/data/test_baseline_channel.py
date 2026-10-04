"""Offline tests for metadata-only discovery and guarded channel remeasurement."""

from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest

from calvino.data import baseline_channel as diagnostic
from calvino.data.baseline_metrics import CHANNELS, CallSlice
from calvino.data.baseline_source import TABLE_COLUMNS
from calvino.data.inventory_access import InventoryError


def _input() -> bytes:
    columns = TABLE_COLUMNS["call_center_interactions"]
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=columns)
    writer.writeheader()
    for identifier, channel, reason in (
        ("synthetic-1", "Phone", "Transaccional"),
        ("synthetic-2", "Voice", "Queja"),
    ):
        writer.writerow(
            {
                "interaction_id": identifier,
                "customer_id": "synthetic-customer",
                "interaction_date": "2024-01-01",
                "reason_category": reason,
                "channel": channel,
                "was_resolved": "true",
                "was_escalated": "false",
                "requires_followup": "false",
                "duration_seconds": "10",
                "wait_time_seconds": "5",
            }
        )
    return stream.getvalue().encode()


class FakeS3:
    """Yield one invented object and record whether a full-body GET happened."""

    def __init__(self) -> None:
        self.content = _input()
        self.prefixes: list[str] = []
        self.gets = 0
        self.body: io.BytesIO | None = None

    def get_paginator(self, name: str) -> FakeS3:
        assert name == "list_objects_v2"
        return self

    def paginate(self, *, Bucket: str, Prefix: str, PaginationConfig: dict) -> list[dict]:
        self.prefixes.append(Prefix)
        if Prefix.endswith(".csv"):
            return [
                {"Contents": [{"Key": Prefix, "Size": len(self.content), "ETag": "synthetic-etag"}]}
            ]
        return [{"Contents": []}]

    def get_object(self, **kwargs: str) -> dict:
        self.gets += 1
        assert kwargs["IfMatch"] == "synthetic-etag"
        self.body = io.BytesIO(self.content)
        return {"Body": self.body}


def _previous(path: Path) -> None:
    groups: dict[tuple[str, str], CallSlice] = {}
    for population, channel in (
        ("all interactions", "Phone"),
        ("Transaccional", "Phone"),
        ("all interactions", "(other)"),
    ):
        measure = CallSlice()
        measure.add(
            {
                "was_resolved": "true",
                "was_escalated": "false",
                "requires_followup": "false",
                "duration_seconds": "10",
                "wait_time_seconds": "5",
            }
        )
        groups[population, channel] = measure
    rows = [
        {"population": population, "slice_type": "channel", "slice_value": channel, **cell}
        for (population, channel), measure in groups.items()
        for cell in measure.rows()
    ]
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def test_manifest_lists_one_table_without_any_get() -> None:
    client = FakeS3()
    reviewed = diagnostic.manifest(client, "synthetic-bucket")
    assert client.prefixes == [
        "data/call_center_interactions.csv",
        "data/call_center_interactions/",
    ]
    assert client.gets == 0
    assert reviewed.summary()["total_bytes"] == len(client.content)
    assert set(reviewed.summary()["tables"]) == {"call_center_interactions"}
    assert "synthetic-bucket" not in str(reviewed.summary())


def test_new_channel_label_does_not_change_original_reconciliation() -> None:
    assert "Web Chat" in CHANNELS
    assert "Web Chat" not in diagnostic.ORIGINAL_CHANNELS


def test_guarded_channel_scan_reconciles_without_touching_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(diagnostic, "EXPECTED_CALLS", 2)
    monkeypatch.setattr(diagnostic, "MIN_LABEL_COUNT", 1)
    client = FakeS3()
    reviewed = diagnostic.manifest(client, "synthetic-bucket")
    original = tmp_path / "old.csv"
    _previous(original)
    stage = tmp_path / "data" / "channel-diagnostic"
    with pytest.raises(InventoryError, match="manifest changed"):
        diagnostic.scan(
            client,
            "synthetic-bucket",
            reviewed,
            digest="not-reviewed",
            max_bytes=len(client.content),
            stage=stage,
            old_path=original,
            root=tmp_path,
        )
    with pytest.raises(InventoryError, match="byte ceiling"):
        diagnostic.scan(
            client,
            "synthetic-bucket",
            reviewed,
            digest=reviewed.digest,
            max_bytes=len(client.content) - 1,
            stage=stage,
            old_path=original,
            root=tmp_path,
        )
    assert client.gets == 0
    result = diagnostic.scan(
        client,
        "synthetic-bucket",
        reviewed,
        digest=reviewed.digest,
        max_bytes=len(client.content),
        stage=stage,
        old_path=original,
        root=tmp_path,
    )
    assert result == {
        "calls": 2,
        "bytes_read": len(client.content),
        "channel_labels": 2,
        "residual_calls": 0,
        "cells_compared": 27,
        "mismatches": 0,
    }
    assert client.gets == 1 and client.body and client.body.closed
    with (stage / "channels.csv").open(encoding="utf-8") as output:
        labels = {row["slice_value"] for row in csv.DictReader(output)}
    assert labels == {"Phone", "Voice"}
    assert original.is_file()
    with pytest.raises(InventoryError, match="not empty"):
        diagnostic.scan(
            FakeS3(),
            "synthetic-bucket",
            reviewed,
            digest=reviewed.digest,
            max_bytes=len(client.content),
            stage=stage,
            old_path=original,
            root=tmp_path,
        )


def test_null_metric_still_reconciles_its_denominators() -> None:
    measure = CallSlice()
    measure.add(
        {
            "was_resolved": "true",
            "was_escalated": "false",
            "requires_followup": "false",
            "duration_seconds": None,
            "wait_time_seconds": None,
        }
    )
    previous = {
        ("all interactions", "Phone", cell["metric"]): {
            "n_population": str(cell["n_population"]),
            "n_valid": str(cell["n_valid"]),
            "n_null_excluded": str(cell["n_null_excluded"]),
            "n_invalid_excluded": str(cell["n_invalid_excluded"]),
            "value": "" if cell["value"] is None else str(cell["value"]),
        }
        for cell in measure.rows()
    }
    previous["all interactions", "Phone", "duration_seconds_mean"]["n_valid"] = "1"
    reconciled = diagnostic._compare(previous, {("all interactions", "Phone"): measure})
    assert sum(not row["matches"] for row in reconciled) == 1
