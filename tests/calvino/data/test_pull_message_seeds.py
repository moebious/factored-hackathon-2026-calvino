"""Offline tests for scripts/pull_message_seeds.py (synthetic only, no network)."""

from __future__ import annotations

import runpy
from pathlib import Path

import pytest


def _script() -> object:
    script = Path(__file__).resolve().parents[3] / "scripts" / "pull_message_seeds.py"
    module = runpy.run_path(str(script))
    return module


S3Lakehouse = _script()["S3Lakehouse"]
_parse_amount = _script()["_parse_amount"]
_parse_day = _script()["_parse_day"]
_parse_flag = _script()["_parse_flag"]
main = _script()["main"]


class FakeBody:
    """In-memory S3 body returning CSV bytes."""

    def __init__(self, text: str) -> None:
        self._data = text.encode("utf-8")

    def read(self, *args: object) -> bytes:
        data, self._data = self._data, b""
        return data

    def close(self) -> None:
        pass


class FakeObject:
    def __init__(self, table: str, key: str, size: int, etag: str = "etag-1") -> None:
        self.table = table
        self.key = key
        self.size = size
        self.etag = etag


class FakeManifest:
    def __init__(self, objects: list[FakeObject]) -> None:
        self.objects = objects


class FakeS3:
    """Minimal S3 double serving fixed CSV payloads by key."""

    def __init__(self, payloads: dict[str, str]) -> None:
        self.payloads = payloads
        self.keys: list[str] = []

    def get_object(self, Bucket: str, Key: str, IfMatch: str) -> dict[str, FakeBody]:
        assert IfMatch == "etag-1"
        self.keys.append(Key)
        return {"Body": FakeBody(self.payloads[Key])}


CUSTOMERS = "customer_id,country\nC-1,México\nC-2,Colombia\n"

TRANSACTIONS = (
    "transaction_id,customer_id,transaction_date,transaction_status,"
    "currency,transaction_type,amount,is_fraud,channel\n"
    "T-1,C-1,2024-03-01,Pending,MXN,Transfer,1200.5,false,app\n"
    "T-2,C-2,2024-04-01,Approved,COP,Payment,,,\n"
)


def _lakehouse() -> S3Lakehouse:
    payloads = {
        "data/customers.csv": CUSTOMERS,
        "data/transactions.csv": TRANSACTIONS,
    }
    objects = [
        FakeObject("customers", "data/customers.csv", len(payloads["data/customers.csv"].encode())),
        FakeObject(
            "transactions",
            "data/transactions.csv",
            len(payloads["data/transactions.csv"].encode()),
        ),
    ]
    return S3Lakehouse(FakeS3(payloads), "synthetic-bucket", FakeManifest(objects))


def test_parse_day_accepts_iso_dates_and_rejects_garbage() -> None:
    from datetime import date

    assert _parse_day("2024-03-01") == date(2024, 3, 1)
    assert _parse_day("  ") is None
    assert _parse_day("not-a-date") is None
    assert _parse_day(None) is None


def test_parse_amount_returns_flag_on_garbage() -> None:
    assert _parse_amount("1200.5") == (1200.5, False)
    assert _parse_amount("") == (None, False)
    assert _parse_amount(None) == (None, False)
    assert _parse_amount("lots") == (None, True)


def test_parse_flag_never_guesses_unknown_values() -> None:
    assert _parse_flag("true") == (True, False)
    assert _parse_flag("False") == (False, False)
    assert _parse_flag("") == (None, False)
    assert _parse_flag(None) == (None, False)
    assert _parse_flag("maybe") == (None, True)


def test_lakehouse_adapter_parses_rows_and_counts_skips() -> None:
    lakehouse = _lakehouse()
    customers = list(lakehouse.iter_customers())
    assert len(customers) == 2
    transactions = list(lakehouse.iter_transactions())
    assert len(transactions) == 2
    assert transactions[0]["transaction_date"] is not None
    assert transactions[0]["amount"] == 1200.5
    assert transactions[0]["is_fraud"] is False
    assert transactions[1]["amount"] is None
    assert lakehouse.transferred > 0


def test_lakehouse_adapter_rejects_missing_columns() -> None:
    payloads = {"data/customers.csv": "customer_id\nC-1\n"}
    size = len(payloads["data/customers.csv"].encode())
    objects = [FakeObject("customers", "data/customers.csv", size)]
    lakehouse = S3Lakehouse(FakeS3(payloads), "synthetic-bucket", FakeManifest(objects))
    with pytest.raises(Exception, match="missing seed columns"):
        list(lakehouse.iter_customers())


def test_run_requires_reviewed_manifest_and_ceiling(tmp_path: Path) -> None:
    assert main(["--run"]) == 2
    assert main(["--run", "--manifest-digest", "abc"]) == 2


def test_check_access_fails_closed_without_credentials(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CALVINO_ENV_FILE", raising=False)
    assert main(["--check-access"]) == 1
    assert "error=" in capsys.readouterr().err
