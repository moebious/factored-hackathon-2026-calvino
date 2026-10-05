"""Pull T-106 seed registries from the live lakehouse (TSD-019).

Read-only: discovers the manifest, enforces the reviewed digest and byte
ceiling before any row is read, then streams customers, transactions and
complaints into ``candidates_from_lakehouse`` and draws the P1 composition
with ``pull_seeds``. Committed output is facts-only seed rows; record
pointers and the per-version salt stay in git-ignored ``data/`` files.

Typical invocation (credentials live in a private file outside the repo)::

    export CALVINO_ENV_FILE="$HOME/.config/calvino/.env"
    uv run python scripts/pull_message_seeds.py --check-access   # one-byte probe
    uv run python scripts/pull_message_seeds.py --manifest      # metadata only
    uv run python scripts/pull_message_seeds.py --run \\
        --manifest-digest DIGEST_FROM_MANIFEST \\
        --max-source-bytes REVIEWED_BYTE_CEILING
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from calvino.data.inventory_access import (  # noqa: E402
    InventoryError,
    discover,
    load_credentials,
    probe,
    s3_client,
)
from calvino.data.inventory_report import check_budget  # noqa: E402
from calvino.data.message_set import gate_table_hash  # noqa: E402
from calvino.data.pull_report import write_pull_report  # noqa: E402
from calvino.data.seed_pull import (  # noqa: E402
    NO_RECORD_NOMINAL,
    SeedShortfall,
    candidates_from_lakehouse,
    pull_seeds,
)
from calvino.data.seed_registry import (  # noqa: E402
    DEFAULT_PROMPT_IDS,
    build_nominal_seeds,
    build_registry,
    commit_pull_outputs,
    ensure_salt,
)
from calvino.policy.config import load_policy  # noqa: E402

TABLES = ("customers", "transactions", "complaints")

# Allowlisted columns per table: the exact fields ``candidates_from_lakehouse``
# reads. Anything else on the wire is dropped before parsing.
COLUMNS: dict[str, tuple[str, ...]] = {
    "customers": ("customer_id", "country"),
    "transactions": (
        "transaction_id",
        "customer_id",
        "transaction_date",
        "transaction_status",
        "currency",
        "transaction_type",
        "amount",
        "is_fraud",
        "channel",
    ),
    "complaints": (
        "complaint_id",
        "customer_id",
        "creation_date",
        "category",
        "status",
        "sla_breached",
    ),
}

_TRUE = {"true", "1", "t", "yes", "y"}
_FALSE = {"false", "0", "f", "no", "n", ""}


def _parse_day(value: object) -> date | None:
    """Parse an ISO date or datetime string; None when absent or unparseable."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            try:
                return datetime.fromisoformat(value.strip()).date()
            except ValueError:
                return None
    return None


def _parse_amount(value: object) -> tuple[float | None, bool]:
    """Parse a decimal amount; the flag reports an unparseable non-empty value."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None, False
    if isinstance(value, bool):
        return None, True
    try:
        return float(value), False  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None, True


def _parse_flag(value: object) -> tuple[bool | None, bool]:
    """Parse a tri-state flag; unknown non-empty values are refused, not guessed."""
    if value is None:
        return None, False
    if isinstance(value, bool):
        return value, False
    text = str(value).strip().lower()
    if text in _TRUE:
        return True, False
    if text in _FALSE:
        return False if text else None, False
    return None, True


class S3Lakehouse:
    """The ``LakehouseSource`` protocol over live S3 objects (read-only).

    Every object is fetched with its manifest ETag and its length is checked
    after the read; ``transferred`` accumulates bytes for the final report.
    """

    def __init__(self, s3: object, bucket: str, manifest: object) -> None:
        self._s3 = s3
        self._bucket = bucket
        self._manifest = manifest
        self.transferred = 0
        self.skipped: dict[str, int] = {}

    def _rows(self, table: str) -> object:
        from calvino.data.inventory_access import SourceManifest

        manifest: SourceManifest = self._manifest  # type: ignore[assignment]
        for obj in manifest.objects:
            if obj.table != table:
                continue
            try:
                body = self._s3.get_object(  # type: ignore[union-attr]
                    Bucket=self._bucket, Key=obj.key, IfMatch=obj.etag
                )["Body"]
            except Exception as error:
                from calvino.data.inventory_access import _safe_error

                raise _safe_error(error) from None  # type: ignore[arg-type]
            read = body.read()
            body.close()
            if len(read) != obj.size:
                raise InventoryError("source object length changed during seed read")
            self.transferred += len(read)
            try:
                text = io.TextIOWrapper(io.BytesIO(read), encoding="utf-8-sig", newline="")
                reader = csv.DictReader(text)
                header = reader.fieldnames or []
                missing = [c for c in COLUMNS[table] if c not in header]
                if missing:
                    raise InventoryError(f"missing seed columns in {table}: {missing}")
                for row in reader:
                    yield {name: row.get(name) for name in COLUMNS[table]}
            except InventoryError:
                raise
            except (csv.Error, OSError, UnicodeError, ValueError) as error:
                raise InventoryError(f"could not read seed table {table}") from error

    def iter_customers(self) -> object:
        return self._rows("customers")

    def iter_transactions(self) -> object:
        for row in self._rows("transactions"):
            typed = dict(row)
            typed["transaction_date"] = _parse_day(row.get("transaction_date"))
            amount, bad = _parse_amount(row.get("amount"))
            if bad:
                self.skipped["transaction:bad-amount"] = (
                    self.skipped.get("transaction:bad-amount", 0) + 1
                )
                continue
            typed["amount"] = amount
            flag, bad = _parse_flag(row.get("is_fraud"))
            if bad:
                self.skipped["transaction:bad-fraud-flag"] = (
                    self.skipped.get("transaction:bad-fraud-flag", 0) + 1
                )
                continue
            typed["is_fraud"] = flag
            yield typed

    def iter_complaints(self) -> object:
        for row in self._rows("complaints"):
            typed = dict(row)
            typed["creation_date"] = _parse_day(row.get("creation_date"))
            flag, bad = _parse_flag(row.get("sla_breached"))
            typed["sla_breached"] = None if bad else flag
            yield typed


def main(argv: list[str] | None = None) -> int:
    """Pull seed registries from the live lakehouse into committed files."""
    parser = argparse.ArgumentParser(description="Pull T-106 seed registries (read-only)")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-access", action="store_true")
    mode.add_argument("--manifest", action="store_true")
    mode.add_argument("--run", action="store_true")
    parser.add_argument("--manifest-digest")
    parser.add_argument("--max-source-bytes", type=int)
    parser.add_argument("--salt-file", type=Path, default=Path("data/message-set-salt-v1"))
    parser.add_argument(
        "--pointer-log", type=Path, default=Path("data/message-set-pointers-v1.jsonl")
    )
    parser.add_argument("--seeds-dir", type=Path, default=Path("evaluation/message-set/v1"))
    parser.add_argument(
        "--pull-report",
        type=Path,
        default=None,
        help="committed pull evidence (defaults to <seeds-dir>/pull-report.json)",
    )
    parser.add_argument("--set-version", default="v1")
    parser.add_argument("--policy", type=Path, default=None)
    parser.add_argument("--rng-seed", type=int, default=20261005)
    args = parser.parse_args(argv)
    if args.run and (not args.manifest_digest or args.max_source_bytes is None):
        print("error=run_requires_reviewed_manifest_and_byte_ceiling", file=sys.stderr)
        return 2
    try:
        bucket = load_credentials()
        s3 = s3_client()
        if args.check_access:
            probe(s3, bucket)
            print("access=ok")
            return 0
        manifest = discover(s3, bucket, tables=TABLES)
        if args.manifest:
            print(
                json.dumps(
                    {
                        "total_bytes": manifest.total_bytes,
                        "digest": manifest.digest,
                        "tables": {name: manifest.summary()["tables"][name] for name in TABLES},
                    },
                    indent=2,
                )
            )
            return 0
        check_budget(
            manifest,
            digest=args.manifest_digest,
            max_bytes=args.max_source_bytes,
            tables=TABLES,
        )
        policy = load_policy(args.policy) if args.policy else load_policy()
        gate = dict(policy.gate.allow_amount_limit)
        hard = dict(policy.hard_rules.amount_limit)
        source = S3Lakehouse(s3, bucket, manifest)
        candidates, skipped = candidates_from_lakehouse(source)  # type: ignore[arg-type]
        for reason, count in sorted(source.skipped.items()):
            skipped[reason] = skipped.get(reason, 0) + count
        drawn, report = pull_seeds(candidates, gate=gate, hard=hard, rng_seed=args.rng_seed)
        salt = ensure_salt(args.salt_file)
        rows, pointers = build_registry(
            [item for split in ("train", "calibration", "test") for item in drawn[split]],
            salt=salt,
            set_version=args.set_version,
            policy_version="v2",
            gate_limits=gate,
            prompt_ids=dict(DEFAULT_PROMPT_IDS),
        )
        for split in ("train", "calibration", "test"):
            # Nominal no-record rows fill only their own quota cell: they
            # never backfill a record-backed shortfall (fail-closed above).
            nominal_rows, nominal_pointers = build_nominal_seeds(
                split,
                NO_RECORD_NOMINAL[split],
                salt=salt,
                set_version=args.set_version,
                policy_version="v2",
            )
            rows.extend(nominal_rows)
            pointers.extend(nominal_pointers)
        by_split: dict[str, list] = {"train": [], "calibration": [], "test": []}
        for row in rows:
            by_split[row.split].append(row)
        # Pointer log first: commit_pull_outputs aborts before touching
        # any registry when the log guard refuses.
        counts = commit_pull_outputs(args.seeds_dir, args.pointer_log, by_split, pointers)
        report_path = args.pull_report or (args.seeds_dir / "pull-report.json")
        write_pull_report(
            report_path,
            report,
            skipped,
            manifest_digest=manifest.digest,
            rng_seed=args.rng_seed,
            policy_version=str(policy.version),
            gate_table_hash=gate_table_hash(gate),
        )
        summary = {
            "considered": dict(report.considered),
            "usable": dict(report.usable),
            "drawn": dict(counts),
            "excluded": dict(report.excluded),
            "skipped": dict(sorted(skipped.items())),
            "notes": list(report.notes),
            "transferred_bytes": source.transferred,
            "seeds_dir": str(args.seeds_dir),
        }
        print(json.dumps(summary, indent=2))
        return 0
    except InventoryError as error:
        print(f"error={error}", file=sys.stderr)
        return 1
    except SeedShortfall as error:
        print(f"error=seed-shortfall: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
