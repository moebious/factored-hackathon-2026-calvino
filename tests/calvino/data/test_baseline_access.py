"""Synthetic tests for four-table read-only discovery, without credentials or S3."""

from __future__ import annotations

import pytest

from calvino.data.inventory_access import InventoryError, discover
from calvino.data.inventory_report import check_budget

BASELINE_TABLES = (
    "customers",
    "call_center_interactions",
    "complaints",
    "daily_exchange_rates",
)


class FakeS3:
    """Return one invented object per requested single-file table."""

    def __init__(self) -> None:
        self.prefixes: list[str] = []

    def get_paginator(self, method: str) -> FakeS3:
        assert method == "list_objects_v2"
        return self

    def paginate(self, *, Bucket: str, Prefix: str, PaginationConfig: dict) -> list[dict]:
        self.prefixes.append(Prefix)
        if Prefix.endswith(".csv"):
            return [{"Contents": [{"Key": Prefix, "Size": 10, "ETag": "synthetic"}]}]
        return [{"Contents": []}]


def test_only_four_baseline_tables_are_discovered() -> None:
    client = FakeS3()
    manifest = discover(client, "synthetic-bucket", tables=BASELINE_TABLES)
    assert {obj.table for obj in manifest.objects} == set(BASELINE_TABLES)
    assert set(manifest.summary()["tables"]) == set(BASELINE_TABLES)
    assert manifest.total_bytes == 40
    assert len(client.prefixes) == 8
    assert all(any(name in prefix for name in BASELINE_TABLES) for prefix in client.prefixes)
    check_budget(manifest, digest=manifest.digest, max_bytes=40)
    with pytest.raises(InventoryError, match="byte ceiling"):
        check_budget(manifest, digest=manifest.digest, max_bytes=39)


@pytest.mark.parametrize("tables", [(), ("customers", "customers"), ("unlisted",)])
def test_unknown_or_duplicate_requests_fail_without_listing(tables: tuple[str, ...]) -> None:
    client = FakeS3()
    with pytest.raises(InventoryError, match="allowlisted"):
        discover(client, "synthetic-bucket", tables=tables)
    assert client.prefixes == []
