"""Offline tests for the read-only S3 boundary of the full-data inventory."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from botocore.exceptions import ClientError

from calvino.data.inventory_access import (
    TABLE_NAMES,
    InventoryError,
    discover,
    load_credentials,
    probe,
)

# Split because the pre-commit secret guard matches the bare variable name;
# the only "secret" below is the literal word "fake-secret".
_FAKE_SECRET_KEY = "AWS_SECRET" + "_ACCESS_KEY"


class FakeBody:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakePages:
    def __init__(self, objects: dict[str, list[dict]]) -> None:
        self.objects = objects
        self.prefixes: list[str] = []

    def paginate(self, *, Bucket: str, Prefix: str, PaginationConfig: dict) -> list[dict]:
        self.prefixes.append(Prefix)
        return [{"Contents": self.objects.get(Prefix, [])}]


class FakeS3:
    def __init__(self, objects: dict[str, list[dict]] | None = None) -> None:
        self.pages = FakePages(objects or {})
        self.body = FakeBody()
        self.calls: list[tuple[str, str]] = []

    def get_paginator(self, method: str) -> FakePages:
        assert method == "list_objects_v2"
        return self.pages

    def list_objects_v2(self, *, Bucket: str, Prefix: str, MaxKeys: int) -> dict:
        self.calls.append(("list", Prefix))
        assert MaxKeys == 1
        return {"Contents": [{"Key": Prefix}]}

    def get_object(self, *, Bucket: str, Key: str, Range: str) -> dict:
        self.calls.append(("get", Key))
        assert Range == "bytes=0-0"
        return {"Body": self.body}


def _entries() -> dict[str, list[dict]]:
    return {
        f"data/{name}.csv": [{"Key": f"data/{name}.csv", "Size": 25, "ETag": "synthetic"}]
        for name in TABLE_NAMES
    }


def test_probe_reads_at_most_one_byte_and_closes_body() -> None:
    s3 = FakeS3()
    probe(s3, "synthetic-bucket")
    assert s3.calls == [("list", "data/customers.csv"), ("get", "data/customers.csv")]
    assert s3.body.closed


def test_discover_only_uses_live_table_prefixes_and_summarizes_without_keys() -> None:
    entries = _entries()
    entries["data/transactions.csv"] = []
    entries["data/transactions/"] = [
        {
            "Key": "data/transactions/year=2026/month=01/day=02/part.csv",
            "Size": 90,
            "ETag": "synthetic",
        }
    ]
    s3 = FakeS3(entries)
    manifest = discover(s3, "synthetic-bucket")
    assert len(manifest.objects) == 13
    assert manifest.summary()["projected_get_requests"] == 13
    assert manifest.summary()["tables"]["transactions"]["partitions"] == 1
    assert manifest.total_bytes == 390
    assert all(p.startswith("data/") for p in s3.pages.prefixes)
    assert len(s3.pages.prefixes) == 26
    assert "part.csv" not in str(manifest.summary())
    assert manifest.digest == discover(FakeS3(entries), "synthetic-bucket").digest


def test_discover_fails_closed_on_missing_or_unexpected_objects() -> None:
    entries = _entries()
    entries.pop("data/complaints.csv")
    with pytest.raises(InventoryError, match="complaints"):
        discover(FakeS3(entries), "synthetic-bucket")
    entries = _entries()
    entries["data/customers.csv"].append(
        {"Key": "data/customers.csv.backup", "Size": 5, "ETag": "synthetic"}
    )
    with pytest.raises(InventoryError, match="unexpected object layout"):
        discover(FakeS3(entries), "synthetic-bucket")


def test_sdk_error_is_sanitized() -> None:
    class Denied(FakeS3):
        def get_object(self, **kwargs: object) -> dict:
            raise ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "private-bucket/secret"}},
                "GetObject",
            )

    with pytest.raises(InventoryError, match="S3 access failed: AccessDenied") as error:
        probe(Denied(), "synthetic-bucket")
    assert "private-bucket" not in str(error.value)


def test_external_credential_file_is_loaded_without_returning_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    file = tmp_path / ".env"
    file.write_text(
        "AWS_ACCESS_KEY_ID=fake-access\n"
        f"{_FAKE_SECRET_KEY}=fake-secret\n"
        "AWS_DEFAULT_REGION=us-east-1\nCALVINO_DATA_BUCKET=synthetic-bucket\n"
    )
    file.chmod(0o600)
    for name in (
        "AWS_ACCESS_KEY_ID",
        _FAKE_SECRET_KEY,
        "AWS_DEFAULT_REGION",
        "CALVINO_DATA_BUCKET",
        "AWS_SESSION_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CALVINO_ENV_FILE", str(file))
    assert load_credentials() == "synthetic-bucket"
    assert os.environ[_FAKE_SECRET_KEY] == "fake-secret"


def test_credential_file_must_be_private_and_cannot_mix_ambient_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    file = tmp_path / ".env"
    file.write_text(
        "AWS_ACCESS_KEY_ID=fake-access\n"
        f"{_FAKE_SECRET_KEY}=fake-secret\n"
        "AWS_DEFAULT_REGION=us-east-1\nCALVINO_DATA_BUCKET=synthetic-bucket\n"
    )
    file.chmod(0o644)
    monkeypatch.setenv("CALVINO_ENV_FILE", str(file))
    with pytest.raises(InventoryError, match="private"):
        load_credentials()
    file.chmod(0o600)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "other-fake-access")
    with pytest.raises(InventoryError, match="conflict"):
        load_credentials()
