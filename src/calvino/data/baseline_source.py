"""Four-table, projected baseline reader for local CSV/Parquet and versioned S3 CSV.

S3 input is streamed directly to aggregation. It is never copied to a local file,
and the caller must approve the exact manifest digest and full transfer byte ceiling.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import duckdb
from botocore.exceptions import BotoCoreError, ClientError
from pydantic import ValidationError

from calvino.data.contracts import TABLES
from calvino.data.inventory_access import InventoryError, SourceManifest, _safe_error
from calvino.data.inventory_report import check_budget

TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "customers": ("customer_id", "country", "segment"),
    "daily_exchange_rates": ("date", "source_currency", "target_currency", "exchange_rate"),
    "call_center_interactions": (
        "interaction_id",
        "customer_id",
        "interaction_date",
        "reason_category",
        "contact_reason",
        "channel",
        "was_resolved",
        "was_escalated",
        "requires_followup",
        "duration_seconds",
        "wait_time_seconds",
    ),
    "complaints": (
        "complaint_id",
        "customer_id",
        "category",
        "case_type",
        "status",
        "sla_breached",
        "resolution_days",
        "compensation_granted",
        "claimed_amount",
        "currency",
        "creation_date",
        "origin_interaction_id",
    ),
}
ORDER = ("customers", "daily_exchange_rates", "call_center_interactions", "complaints")


class CountingBody(io.RawIOBase):
    """Count actual CSV bytes consumed and close the underlying streaming response."""

    def __init__(self, body: Any) -> None:
        self.body = body
        self.bytes_read = 0

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: bytearray) -> int:
        chunk = self.body.read(len(buffer))
        length = len(chunk)
        buffer[:length] = chunk
        self.bytes_read += length
        return length

    def close(self) -> None:
        if not self.closed:
            self.body.close()
        super().close()


def _checked(table: str, row: dict[str, str | None]) -> dict[str, str | None]:
    row = {name: value if value != "" else None for name, value in row.items()}
    try:
        TABLES[table].model.model_validate(row)
    except (ValidationError, ValueError, TypeError):
        raise InventoryError(f"invalid contracted record in {table}") from None
    return row


def csv_rows(body: Any, table: str) -> Iterator[dict[str, str | None]]:
    """Close the source body even when a record fails validation."""
    try:
        with io.TextIOWrapper(body, encoding="utf-8-sig", newline="") as text:
            reader = csv.DictReader(text)
            header = reader.fieldnames
            if (
                not header
                or len(header) != len(set(header))
                or set(TABLE_COLUMNS[table]) - set(header)
            ):
                raise InventoryError(f"missing or duplicate baseline columns in {table}")
            for row in reader:
                if None in row:
                    raise InventoryError(f"extra CSV field in {table}")
                yield _checked(table, {name: row[name] for name in TABLE_COLUMNS[table]})
    except InventoryError:
        raise
    except (ClientError, BotoCoreError) as error:
        raise _safe_error(error) from None
    except (csv.Error, OSError, UnicodeError, ValueError):
        raise InventoryError(f"could not read baseline table {table}") from None


def local_rows(directory: Path, table: str) -> Iterator[dict[str, str | None]]:
    """Accept exactly one local source representation per table, without staging."""
    csv_path, parquet_path = (directory / f"{table}.{ext}" for ext in ("csv", "parquet"))
    if csv_path.is_file() == parquet_path.is_file():
        raise InventoryError(f"baseline table {table} is missing or ambiguous")
    if csv_path.is_file():
        try:
            with csv_path.open("rb") as body:
                yield from csv_rows(body, table)
        except OSError:
            raise InventoryError(f"could not read baseline table {table}") from None
        return
    # Only constant, allowlisted identifiers become SQL text; the path is a parameter.
    columns = ", ".join(f'"{name}"' for name in TABLE_COLUMNS[table])
    try:
        with duckdb.connect(":memory:") as con:
            cursor = con.execute(f"SELECT {columns} FROM read_parquet(?)", [str(parquet_path)])
            while batch := cursor.fetchmany(2048):
                for values in batch:
                    row = {
                        name: None if value is None else str(value)
                        for name, value in zip(TABLE_COLUMNS[table], values, strict=True)
                    }
                    yield _checked(table, row)
    except InventoryError:
        raise
    except (duckdb.Error, OSError, ValueError):
        raise InventoryError(f"could not read baseline table {table}") from None


def s3_rows(
    s3: Any,
    bucket: str,
    manifest: SourceManifest,
    table: str,
    *,
    digest: str,
    max_bytes: int,
    transferred: list[int] | None = None,
) -> Iterator[dict[str, str | None]]:
    """Require the same reviewed manifest before each version-matched object read."""
    check_budget(manifest, digest=digest, max_bytes=max_bytes)
    for obj in manifest.objects:
        if obj.table != table:
            continue
        try:
            body = s3.get_object(Bucket=bucket, Key=obj.key, IfMatch=obj.etag)["Body"]
        except (ClientError, BotoCoreError) as error:
            raise _safe_error(error) from None
        counted = CountingBody(body)
        try:
            yield from csv_rows(counted, table)
            if counted.bytes_read != obj.size:
                raise InventoryError("source object length changed during baseline read")
            if transferred is not None:
                transferred[0] += counted.bytes_read
        finally:
            counted.close()
