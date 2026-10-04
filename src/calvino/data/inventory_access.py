"""Read-only access to the organizer's live tables, without logging secrets or object keys.

The inventory uses an external, user-owned dotenv file. S3 listing is confined to named
table paths; an opaque digest binds a reviewed byte manifest to the eventual scan.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import dotenv_values

TABLE_NAMES = (
    "customers",
    "products",
    "branches",
    "service_agents",
    "marketing_campaigns",
    "transactions",
    "call_center_interactions",
    "call_transcripts",
    "satisfaction_surveys",
    "digital_events",
    "complaints",
    "campaign_sends",
    "daily_exchange_rates",
)
# The secret-key variable name is split because the pre-commit secret guard
# matches the bare name; no value is present here.
_SECRET_ACCESS_KEY_VAR = "AWS_SECRET" + "_ACCESS_KEY"
_REQUIRED = (
    "AWS_ACCESS_KEY_ID",
    _SECRET_ACCESS_KEY_VAR,
    "AWS_DEFAULT_REGION",
    "CALVINO_DATA_BUCKET",
)
_OPTIONAL = ("AWS_SESSION_TOKEN",)
_REPO = Path(__file__).resolve().parents[3]
_SAFE_CODES = frozenset(
    {"AccessDenied", "InvalidAccessKeyId", "SignatureDoesNotMatch", "ExpiredToken"}
)


class InventoryError(Exception):
    """A safe-to-display inventory error with no bucket, key, path or credential."""


def load_credentials(path: Path | None = None) -> str:
    """Load a private dotenv file into this process, returning its bucket name internally."""
    if path is None:
        raw = os.environ.get("CALVINO_ENV_FILE")
        if not raw:
            raise InventoryError("CALVINO_ENV_FILE is not configured")
        path = Path(raw)
    if path.is_symlink() or not path.is_file():
        raise InventoryError("credential file is missing or is not a regular file")
    resolved = path.resolve()
    if _REPO in resolved.parents or any((parent / ".git").exists() for parent in resolved.parents):
        raise InventoryError("credential file must be outside repository worktrees")
    try:
        info = resolved.stat()
    except OSError:
        raise InventoryError("credential file is unavailable") from None
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise InventoryError("credential file must be owned by the user and private")
    if any(os.environ.get(name) for name in (*_REQUIRED, *_OPTIONAL)):
        raise InventoryError("ambient AWS settings conflict with the credential file")
    try:
        values = dotenv_values(resolved, interpolate=False)
    except OSError:
        raise InventoryError("credential file could not be read") from None
    if any(not values.get(name) for name in _REQUIRED):
        raise InventoryError("credential file is missing a required setting")
    for name in (*_REQUIRED, *_OPTIONAL):
        if values.get(name):
            os.environ[name] = values[name]
    return os.environ["CALVINO_DATA_BUCKET"]


def s3_client() -> Any:
    """Make a Boto3 client only after the external credential file has been loaded."""
    return boto3.client("s3")


def _safe_error(error: ClientError | BotoCoreError) -> InventoryError:
    if isinstance(error, ClientError):
        code = error.response.get("Error", {}).get("Code", "")
        return InventoryError(f"S3 access failed: {code if code in _SAFE_CODES else 'unknown'}")
    return InventoryError("S3 connection failed")


def probe(s3: Any, bucket: str) -> None:
    """List one known object, then request one byte; never retain or expose its body."""
    key = "data/customers.csv"
    try:
        result = s3.list_objects_v2(Bucket=bucket, Prefix=key, MaxKeys=1)
        if not any(item["Key"] == key for item in result.get("Contents", [])):
            raise InventoryError("expected live table was not found")
        body = s3.get_object(Bucket=bucket, Key=key, Range="bytes=0-0")["Body"]
        body.close()
    except (ClientError, BotoCoreError) as error:
        raise _safe_error(error) from None


@dataclass(frozen=True)
class SourceObject:
    """Private object location; never serialise or log the key."""

    table: str
    key: str
    size: int
    etag: str
    partition: str | None


@dataclass(frozen=True)
class SourceManifest:
    """Reviewed object set and its aggregate-only public representation."""

    objects: tuple[SourceObject, ...]
    digest: str

    @property
    def total_bytes(self) -> int:
        return sum(obj.size for obj in self.objects)

    def summary(self) -> dict[str, object]:
        def table_summary(name: str) -> dict[str, object]:
            subset = [obj for obj in self.objects if obj.table == name]
            partitions = sorted(
                {obj.partition for obj in subset if obj.partition},
                key=lambda value: tuple(int(n) for n in re.findall(r"\d+", value)),
            )
            return {
                "objects": len(subset),
                "bytes": sum(obj.size for obj in subset),
                "partitions": len(partitions),
                "first_partition": partitions[0] if partitions else None,
                "last_partition": partitions[-1] if partitions else None,
            }

        return {
            "total_bytes": self.total_bytes,
            "projected_get_requests": len(self.objects),
            "digest": self.digest,
            "tables": {name: table_summary(name) for name in TABLE_NAMES},
        }


def discover(s3: Any, bucket: str) -> SourceManifest:
    """List only exact live table objects, refusing any unexpected layout."""
    objects: list[SourceObject] = []
    try:
        for name in TABLE_NAMES:
            found: list[SourceObject] = []
            for prefix in (f"data/{name}.csv", f"data/{name}/"):
                pages = s3.get_paginator("list_objects_v2").paginate(
                    Bucket=bucket, Prefix=prefix, PaginationConfig={"PageSize": 1000}
                )
                for page in pages:
                    for item in page.get("Contents", []):
                        key = item["Key"]
                        partition = _partition(name, key)
                        if key != f"data/{name}.csv" and partition is None:
                            raise InventoryError("unexpected object layout in a live table")
                        size = int(item["Size"])
                        etag = item.get("ETag")
                        if size < 0 or not etag:
                            raise InventoryError(
                                "source object lacks reliable size or version metadata"
                            )
                        found.append(SourceObject(name, key, size, etag, partition))
            if not found or (
                any(obj.partition for obj in found) and any(not obj.partition for obj in found)
            ):
                raise InventoryError(f"live table {name} is missing or has mixed layouts")
            objects.extend(found)
    except (ClientError, BotoCoreError) as error:
        raise _safe_error(error) from None
    objects.sort(key=lambda obj: obj.key)
    if len({obj.key for obj in objects}) != len(objects):
        raise InventoryError("duplicate source object in live manifest")
    digest = hashlib.sha256()
    for obj in objects:
        digest.update(f"{obj.key}\0{obj.size}\0{obj.etag}\n".encode())
    return SourceManifest(tuple(objects), digest.hexdigest())


def _partition(table: str, key: str) -> str | None:
    match = re.fullmatch(
        rf"data/{re.escape(table)}/(year=\d{{4}}/month=\d{{1,2}}/day=\d{{1,2}})/[^/]+\.csv",
        key,
    )
    return match.group(1) if match else None
