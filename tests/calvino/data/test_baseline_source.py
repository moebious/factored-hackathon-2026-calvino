"""Offline source and staging tests; all rows come from small synthetic fixtures."""

from __future__ import annotations

import csv
import importlib.util
import io
from pathlib import Path

import duckdb
import pytest

from calvino.data.baseline_source import ORDER, TABLE_COLUMNS, csv_rows, local_rows, s3_rows
from calvino.data.inventory_access import InventoryError, SourceManifest, SourceObject

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "lakehouse"
spec = importlib.util.spec_from_file_location(
    "baseline_runner", Path(__file__).resolve().parents[3] / "scripts" / "baseline" / "run.py"
)
assert spec and spec.loader
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_projection_never_returns_unnamed_csv_columns() -> None:
    with (FIXTURES / "call_center_interactions.csv").open("rb") as body:
        rows = list(csv_rows(body, "call_center_interactions"))
    assert rows
    assert set(rows[0]) == set(TABLE_COLUMNS["call_center_interactions"])
    assert "agent_id" not in rows[0]


def test_csv_and_parquet_yield_identical_projected_rows(tmp_path: Path) -> None:
    for name in ORDER:
        path = FIXTURES / f"{name}.csv"
        with duckdb.connect(":memory:") as con:
            con.execute(
                "CREATE TABLE fixture AS SELECT * FROM read_csv(?, all_varchar=true)", [str(path)]
            )
            destination = str(tmp_path / f"{name}.parquet").replace("'", "''")
            con.execute(f"COPY fixture TO '{destination}' (FORMAT PARQUET)")
        assert list(local_rows(FIXTURES, name)) == list(local_rows(tmp_path, name))


def test_version_guard_prevents_any_body_get_and_stream_closes() -> None:
    content = b"customer_id,country,segment\nsynthetic,M\xc3\xa9xico,Basic\n"
    obj = SourceObject("customers", "data/customers.csv", len(content), "synthetic-etag", None)
    manifest = SourceManifest((obj,), "reviewed-digest")

    class FakeS3:
        calls = 0
        body = io.BytesIO(content)

        def get_object(self, **kwargs: str) -> dict:
            self.calls += 1
            assert kwargs["IfMatch"] == "synthetic-etag"
            return {"Body": self.body}

    s3 = FakeS3()
    with pytest.raises(InventoryError, match="manifest changed"):
        list(
            s3_rows(
                s3, "synthetic-bucket", manifest, "customers", digest="old", max_bytes=len(content)
            )
        )
    with pytest.raises(InventoryError, match="byte ceiling"):
        list(
            s3_rows(
                s3,
                "synthetic-bucket",
                manifest,
                "customers",
                digest="reviewed-digest",
                max_bytes=len(content) - 1,
            )
        )
    assert s3.calls == 0
    assert (
        len(
            list(
                s3_rows(
                    s3,
                    "synthetic-bucket",
                    manifest,
                    "customers",
                    digest="reviewed-digest",
                    max_bytes=len(content),
                )
            )
        )
        == 1
    )
    assert s3.body.closed


def test_local_fixture_stages_candidate_without_overwriting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    stage = tmp_path / "data" / "baseline-staging"
    result = runner.run(str(FIXTURES), stage=stage)
    assert result["status"] == "candidate"
    assert result["rows"]["customers"] == 3
    assert (stage / "interactions.csv").exists()
    assert "synthetic" not in (stage / "README.md").read_text()
    with (stage / "interactions.csv").open() as stream:
        values = list(csv.DictReader(stream))
    assert values and "customer_id" not in values[0]
    with pytest.raises(InventoryError, match="not empty"):
        runner.run(str(FIXTURES), stage=stage)


def test_check_access_only_probes_and_lists_four_tables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeClient:
        prefixes: list[str] = []
        gets: list[dict] = []

        def list_objects_v2(self, **kwargs: object) -> dict:
            assert kwargs["MaxKeys"] == 1
            return {"Contents": [{"Key": "data/customers.csv"}]}

        def get_object(self, **kwargs: object) -> dict:
            self.gets.append(kwargs)
            assert kwargs["Range"] == "bytes=0-0"
            return {"Body": io.BytesIO(b"x")}

        def get_paginator(self, method: str) -> FakeClient:
            assert method == "list_objects_v2"
            return self

        def paginate(self, **kwargs: object) -> list[dict]:
            prefix = kwargs["Prefix"]
            self.prefixes.append(prefix)
            if prefix.endswith(".csv"):
                return [{"Contents": [{"Key": prefix, "Size": 10, "ETag": "fake"}]}]
            return [{"Contents": []}]

    client = FakeClient()
    monkeypatch.setattr(runner, "load_credentials", lambda: "private-bucket")
    monkeypatch.setattr(runner, "s3_client", lambda: client)
    summary = runner.run("live-s3", check_access=True, stage=tmp_path / "unused")
    assert summary["total_bytes"] == 40
    assert len(client.prefixes) == 8
    assert len(client.gets) == 1
    assert "private-bucket" not in str(summary)
    assert "data/customers.csv" not in str(summary)
    assert not (tmp_path / "unused").exists()
    with pytest.raises(InventoryError, match="manifest changed"):
        runner.run("live-s3", digest="wrong", max_bytes=40, stage=tmp_path / "unused")
    assert len(client.gets) == 2  # one-byte probe, still no full-object GET


def test_staging_refuses_outside_path_without_creating_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner, "ROOT", tmp_path / "worktree")
    outside = tmp_path / "outside"
    with pytest.raises(InventoryError, match="staging must"):
        runner.run(str(FIXTURES), stage=outside)
    assert not outside.exists()
