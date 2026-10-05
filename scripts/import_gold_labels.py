#!/usr/bin/env python3
"""Preview or apply maintainer-entered T-107 classifier labels."""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import os
import stat
import sys
import tempfile
import unicodedata
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from calvino.data.labels import GoldLabels, validate_gold_record  # noqa: E402

DEFAULT_CSV = ROOT / "data" / "T-107-gold-classifier-labels.csv"
DEFAULT_TEMPLATE = ROOT / "docs" / "templates" / "T-107-gold-classifier-labels.csv"
DEFAULT_GOLD = ROOT / "tests" / "fixtures" / "gold" / "gold-050.jsonl"
CSV_FIELDS = (
    "gold_id",
    "message",
    "language_variant",
    "workflow_area",
    "stuck_intent",
    "clear_enough",
    "needs_person",
    "injection",
    "annotator",
    "labelled_at",
    "notes",
)
LABEL_FIELDS = ("workflow_area", "stuck_intent", "clear_enough", "needs_person", "injection")


def _read_records(gold_path: Path) -> tuple[str, dict[str, dict], list[str]]:
    """Load and validate the gold JSONL while preserving row order."""
    original = gold_path.read_text(encoding="utf-8")
    records: dict[str, dict] = {}
    order: list[str] = []
    for line_number, line in enumerate(original.splitlines(), 1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid JSONL at line {line_number}: {error.msg}") from error
        record = validate_gold_record(data)
        if record.gold_id in records:
            raise ValueError(f"duplicate gold_id in JSONL: {record.gold_id}")
        records[record.gold_id] = data
        order.append(record.gold_id)
    return original, records, order


def _check_identity(annotation: dict[str, str], record: dict, gold_id: str) -> None:
    """Reject a worksheet row that no longer identifies its source message."""
    for field in ("message", "language_variant"):
        worksheet_value = unicodedata.normalize("NFC", annotation.get(field, "").strip())
        gold_value = unicodedata.normalize("NFC", record[field].strip())
        if worksheet_value != gold_value:
            raise ValueError(f"{gold_id}: worksheet {field} does not match the gold JSONL")


def _validate_label_date(value: str, gold_id: str) -> None:
    """Require a supplied classifier-label date to use ISO format."""
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{gold_id}: labelled_at must be an ISO date (YYYY-MM-DD)") from error
    if parsed.isoformat() != value:
        raise ValueError(f"{gold_id}: labelled_at must be an ISO date (YYYY-MM-DD)")


def prepare_import(csv_path: Path, gold_path: Path) -> tuple[str, str, int, int]:
    """Validate a worksheet and return a proposed JSONL merge in memory."""
    original, records, order = _read_records(gold_path)
    with csv_path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if tuple(reader.fieldnames or ()) != CSV_FIELDS:
            raise ValueError(f"worksheet columns must match the T-107 contract: {CSV_FIELDS!r}")
        annotations = list(reader)

    seen: set[str] = set()
    changed_fields = 0
    for line_number, annotation in enumerate(annotations, 2):
        gold_id = (annotation.get("gold_id") or "").strip()
        if not gold_id:
            raise ValueError(f"missing gold_id in CSV row {line_number}")
        if gold_id in seen:
            raise ValueError(f"duplicate gold_id in CSV: {gold_id}")
        seen.add(gold_id)
        if gold_id not in records:
            raise ValueError(f"unknown gold_id in CSV: {gold_id}")

        record = records[gold_id]
        _check_identity(annotation, record, gold_id)
        supplied = {
            field: (annotation.get(field) or "").strip()
            for field in LABEL_FIELDS
            if (annotation.get(field) or "").strip()
        }
        annotator = (annotation.get("annotator") or "").strip()
        labelled_at = (annotation.get("labelled_at") or "").strip()
        if supplied and (not annotator or not labelled_at):
            raise ValueError(f"{gold_id}: supplied labels require annotator and labelled_at")
        if supplied:
            _validate_label_date(labelled_at, gold_id)
            for field, value in (("annotator", annotator), ("labelled_at", labelled_at)):
                current = record.get(field, "")
                if current and current != value:
                    raise ValueError(
                        f"{gold_id}.{field} already contains {current!r}; refusing to replace it"
                    )

        labels = record.setdefault("labels", {})
        for field, value in supplied.items():
            candidate = GoldLabels.model_validate({**labels, field: value}).model_dump(mode="json")
            validated_value = candidate[field]
            current = labels.get(field)
            if current is not None and current != validated_value:
                raise ValueError(
                    f"{gold_id}.labels.{field} already contains {current!r}; "
                    f"refusing to replace it with {validated_value!r}"
                )
            if current is None:
                labels[field] = validated_value
                changed_fields += 1

        if supplied:
            for field, value in (("annotator", annotator), ("labelled_at", labelled_at)):
                if not record.get(field):
                    record[field] = value
                    changed_fields += 1
        note = (annotation.get("notes") or "").strip()
        if note:
            existing = record.get("notes", "").strip()
            if note not in existing.split("\n\n"):
                record["notes"] = f"{existing}\n\n{note}".strip()
                changed_fields += 1
        validate_gold_record(record)

    missing = set(records) - seen
    if missing:
        raise ValueError(f"worksheet is missing gold_id rows: {', '.join(sorted(missing))}")

    complete = sum(validate_gold_record(records[gold_id]).is_labelled() for gold_id in order)
    rendered = "".join(json.dumps(records[gold_id], ensure_ascii=False) + "\n" for gold_id in order)
    return original, rendered, changed_fields, complete


def _atomic_write(path: Path, content: str) -> None:
    """Write through a same-directory temporary file, then replace atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as destination:
            destination.write(content)
            destination.flush()
            os.fsync(destination.fileno())
        if path.exists():
            os.chmod(temporary_path, stat.S_IMODE(path.stat().st_mode))
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def main(argv: list[str] | None = None) -> int:
    """Print a unified diff; write only when the maintainer passes --apply."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV,
        help="maintainer's working copy (defaults under git-ignored data/)",
    )
    parser.add_argument("--gold-sheet", type=Path, default=DEFAULT_GOLD)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write the validated merge (default is preview only)",
    )
    args = parser.parse_args(argv)
    if not args.csv.is_file():
        parser.error(
            f"worksheet not found at {args.csv}; copy the maintained starting sheet "
            f"from {DEFAULT_TEMPLATE} to that path and fill a working copy"
        )
    try:
        original, merged, changed_fields, complete = prepare_import(args.csv, args.gold_sheet)
    except ValueError as error:
        parser.error(str(error))

    diff = difflib.unified_diff(
        original.splitlines(keepends=True),
        merged.splitlines(keepends=True),
        fromfile=str(args.gold_sheet),
        tofile=f"{args.gold_sheet} (proposed)",
    )
    print("".join(diff) or "No JSONL changes proposed.")
    print(f"Validated worksheet; {changed_fields} new field values; {complete}/50 rows complete.")
    if args.apply:
        _atomic_write(args.gold_sheet, merged)
        print(f"Applied merge to {args.gold_sheet}.")
    else:
        print("Preview only; pass --apply to write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
