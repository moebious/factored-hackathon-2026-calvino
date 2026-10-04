"""Read-only full-data inventory; live execution is a maintainer-run local step.

Examples (CALVINO_ENV_FILE points outside the repository):
  uv run python scripts/full_data_inventory.py --check-access
  uv run python scripts/full_data_inventory.py --manifest
  uv run python scripts/full_data_inventory.py --run \
      --manifest-digest <digest> --max-source-bytes <reviewed-byte-ceiling>

The manifest mode reads object metadata only. The run mode scans every row, writes
only aggregate output to git-ignored data/, and never publishes or deletes files.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

from calvino.data.inventory_access import (
    InventoryError,
    discover,
    load_credentials,
    probe,
    s3_client,
)
from calvino.data.inventory_report import (
    EXPECTED_ROWS,
    TYPE_REVIEW_TABLES,
    build_report,
    check_budget,
    review_type_flags,
)

ROOT = Path(__file__).resolve().parents[1]


def _stage(report: dict[str, object]) -> None:
    relative = Path("data") / "inventory-staging" / uuid.uuid4().hex
    folder = ROOT / relative
    folder.mkdir(mode=0o700, parents=True, exist_ok=False)
    output = folder / "full-inventory.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    output.chmod(0o600)
    lines = [
        "# Full-data inventory (staged for review)",
        "",
        "Aggregate-only, not yet published. Five tables lack contracts; "
        "PK/FK checks are not rerun.",
        "",
        "| Table | Previous rows | Observed rows |",
        "|---|---:|---:|",
    ]
    for name, previous in EXPECTED_ROWS.items():
        lines.append(f"| {name} | {previous:,} | {report['tables'][name]['rows']:,} |")
    lines += ["", f"Unresolved differences: {len(report['discrepancies'])}", ""]
    summary = folder / "README.md"
    summary.write_text("\n".join(lines), encoding="utf-8")
    summary.chmod(0o600)
    print(f"complete=true; staged_report={relative}/full-inventory.json")
    print(f"discrepancies={len(report['discrepancies'])}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only inventory of the 13 live tables")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-access", action="store_true")
    mode.add_argument("--manifest", action="store_true")
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--review-types", action="store_true")
    parser.add_argument("--manifest-digest")
    parser.add_argument("--max-source-bytes", type=int)
    args = parser.parse_args(argv)
    if (args.run or args.review_types) and (
        not args.manifest_digest or args.max_source_bytes is None
    ):
        print("error=run_requires_reviewed_manifest_and_byte_ceiling", file=sys.stderr)
        return 2
    try:
        bucket = load_credentials()
        s3 = s3_client()
        if args.check_access:
            probe(s3, bucket)
            print("access=ok")
            return 0
        manifest = discover(s3, bucket)
        if args.manifest:
            print(json.dumps(manifest.summary(), indent=2))
            return 0
        if args.review_types:
            check_budget(
                manifest,
                digest=args.manifest_digest,
                max_bytes=args.max_source_bytes,
                tables=TYPE_REVIEW_TABLES,
            )
            print(json.dumps(review_type_flags(s3, bucket, manifest), indent=2))
            return 0
        check_budget(manifest, digest=args.manifest_digest, max_bytes=args.max_source_bytes)
        _stage(build_report(s3, bucket, manifest))
        return 0
    except InventoryError as error:
        print(f"error={error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
