#!/usr/bin/env python3
"""Preview or apply maintainer-entered T-103 CSV outcome annotations.

The importer merges only optional oracle facts and human outcome metadata.
It validates the full result, refuses conflicting overwrites, and never
changes classifier labels.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import sys
import unicodedata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from calvino.data.labels import validate_gold_record  # noqa: E402

DEFAULT_CSV = ROOT / "docs" / "templates" / "T-103-gold-outcome-annotations.csv"
DEFAULT_GOLD = ROOT / "tests" / "fixtures" / "gold" / "gold-050.jsonl"

CSV_FIELDS = (
    "gold_id",
    "message",
    "language_variant",
    "record_status",
    "owner",
    "amount_band",
    "fraud_flag",
    "oracle_intent",
    "oracle_ambiguous",
    "oracle_in_scope",
    "human_outcome",
    "outcome_annotator",
    "outcome_labelled_at",
    "notes",
)
FACT_FIELDS = {
    "record_status": "status",
    "owner": "owner",
    "amount_band": "amount_band",
    "fraud_flag": "fraud_flag",
    "oracle_intent": "intent",
    "oracle_ambiguous": "ambiguous",
    "oracle_in_scope": "in_scope",
}
BOOL_FIELDS = {"owner", "fraud_flag", "oracle_ambiguous", "oracle_in_scope"}
OUTCOME_FIELDS = ("human_outcome", "outcome_annotator", "outcome_labelled_at")


def _csv_value(column: str, raw: str) -> Any:
    """Parse a non-empty cell into the strict schema's Python value."""
    value = raw.strip()
    if column in BOOL_FIELDS:
        if value not in {"true", "false"}:
            raise ValueError(f"{column} must be 'true' or 'false', got {raw!r}")
        return value == "true"
    if column == "record_status" and value.lower() == "null":
        return None
    return value


def _merge_value(target: dict[str, Any], key: str, value: Any, *, label: str) -> bool:
    """Set a missing value or accept an identical repeat; reject conflicts."""
    if key in target:
        if target[key] != value:
            raise ValueError(
                f"{label} already contains {target[key]!r}; refusing to replace it with {value!r}"
            )
        return False
    target[key] = value
    return True


def _append_note(record: dict[str, Any], note: str) -> bool:
    """Append a worksheet note once, preserving any existing notes."""
    addition = note.strip()
    if not addition:
        return False
    existing = record.get("notes", "").strip()
    if addition in existing.split("\n\n"):
        return False
    record["notes"] = f"{existing}\n\n{addition}".strip()
    return True


def prepare_import(csv_path: Path, gold_path: Path) -> tuple[str, str, int]:
    """Validate a worksheet and produce a proposed JSONL merge in memory."""
    original = gold_path.read_text(encoding="utf-8")
    rows: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for line_number, line in enumerate(original.splitlines(), 1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid JSONL at line {line_number}: {error.msg}") from error
        record = validate_gold_record(data)
        if record.gold_id in rows:
            raise ValueError(f"duplicate gold_id in JSONL: {record.gold_id}")
        rows[record.gold_id] = data
        order.append(record.gold_id)

    with csv_path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if tuple(reader.fieldnames or ()) != CSV_FIELDS:
            raise ValueError(
                "worksheet columns do not match the outcome-only import contract; "
                f"expected {CSV_FIELDS!r}"
            )
        worksheet_rows = list(reader)

    seen: set[str] = set()
    changed_fields = 0
    for line_number, annotation in enumerate(worksheet_rows, 2):
        gold_id = (annotation.get("gold_id") or "").strip()
        if not gold_id:
            raise ValueError(f"missing gold_id in CSV row {line_number}")
        if gold_id in seen:
            raise ValueError(f"duplicate gold_id in CSV: {gold_id}")
        seen.add(gold_id)
        if gold_id not in rows:
            raise ValueError(f"unknown gold_id in CSV: {gold_id}")
        record = rows[gold_id]
        for identity_field in ("message", "language_variant"):
            worksheet_identity = unicodedata.normalize(
                "NFC", (annotation.get(identity_field) or "").strip()
            )
            gold_identity = unicodedata.normalize("NFC", record[identity_field].strip())
            if worksheet_identity != gold_identity:
                raise ValueError(
                    f"{gold_id}: worksheet {identity_field} does not match the gold JSONL"
                )

        oracle_cells = {
            field: annotation.get(field, "")
            for field in (
                "record_status",
                "owner",
                "amount_band",
                "fraud_flag",
                "oracle_intent",
                "oracle_ambiguous",
                "oracle_in_scope",
            )
        }
        supplied_outcome = {
            field: (annotation.get(field) or "").strip() for field in OUTCOME_FIELDS
        }
        if any(supplied_outcome.values()) and not all(supplied_outcome.values()):
            raise ValueError(
                f"{gold_id}: human_outcome, outcome_annotator and "
                "outcome_labelled_at must be supplied together"
            )

        if any(value.strip() for value in oracle_cells.values()):
            facts = record.setdefault("oracle_facts", {})
            if not isinstance(facts, dict):
                raise ValueError(f"{gold_id}: oracle_facts is not an object")
            for field, raw in oracle_cells.items():
                if not raw.strip():
                    continue
                value = _csv_value(field, raw)
                target_field = FACT_FIELDS[field]
                changed_fields += _merge_value(
                    facts, target_field, value, label=f"{gold_id}.oracle_facts.{target_field}"
                )

        for field, raw in supplied_outcome.items():
            if raw:
                changed_fields += _merge_value(record, field, raw, label=f"{gold_id}.{field}")
        changed_fields += _append_note(record, annotation.get("notes") or "")
        validate_gold_record(record)

    rendered = "".join(json.dumps(rows[gold_id], ensure_ascii=False) + "\n" for gold_id in order)
    return original, rendered, changed_fields


def main(argv: list[str] | None = None) -> int:
    """Print a proposed unified diff; write only when --apply is supplied."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--gold-sheet", type=Path, default=DEFAULT_GOLD)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write the validated merge (default is preview only)",
    )
    args = parser.parse_args(argv)

    original, merged, changed_fields = prepare_import(args.csv, args.gold_sheet)
    diff = difflib.unified_diff(
        original.splitlines(keepends=True),
        merged.splitlines(keepends=True),
        fromfile=str(args.gold_sheet),
        tofile=f"{args.gold_sheet} (proposed)",
    )
    diff_text = "".join(diff)
    print(diff_text or "No JSONL changes proposed.")
    print(f"Validated worksheet; {changed_fields} new field values.")
    if args.apply:
        args.gold_sheet.write_text(merged, encoding="utf-8")
        print(f"Applied merge to {args.gold_sheet}.")
    else:
        print("Preview only; pass --apply to write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
