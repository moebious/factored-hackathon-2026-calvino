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
import os
import stat
import sys
import tempfile
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from calvino.data.labels import validate_gold_record  # noqa: E402

DEFAULT_CSV = ROOT / "docs" / "templates" / "T-103-gold-outcome-annotations.csv"
DEFAULT_GOLD = ROOT / "tests" / "fixtures" / "gold" / "gold-050.jsonl"
DEFAULT_CORRECTION_LEDGER = ROOT / "reports" / "eval" / "T-103-gold-import-corrections.jsonl"

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
REPLACE_FIELDS = {f"oracle_facts.{field}" for field in FACT_FIELDS.values()} | set(OUTCOME_FIELDS)
CSV_FIELD_FOR_PATH = {
    **{f"oracle_facts.{target}": source for source, target in FACT_FIELDS.items()},
    **{field: field for field in OUTCOME_FIELDS},
}


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


def _merge_annotation_value(
    target: dict[str, Any],
    key: str,
    value: Any,
    *,
    gold_id: str,
    field_path: str,
    reasons: dict[tuple[str, str], str],
    used_replacements: set[tuple[str, str]],
    corrections: list[dict[str, Any]],
) -> bool:
    """Merge one supplied value, requiring an explicit reason to replace it."""
    if key not in target:
        target[key] = value
        return True
    old_value = target[key]
    if old_value == value:
        return False

    replacement_key = (gold_id, field_path)
    reason = reasons.get(replacement_key)
    if reason is None:
        raise ValueError(
            f"{gold_id}.{field_path} already contains {old_value!r}; "
            f"refusing to replace it with {value!r}"
        )
    target[key] = value
    used_replacements.add(replacement_key)
    corrections.append(
        {
            "gold_id": gold_id,
            "field": field_path,
            "old_value": old_value,
            "new_value": value,
            "reason": reason,
            "corrected_at": date.today().isoformat(),
        }
    )
    return True


def prepare_import(
    csv_path: Path,
    gold_path: Path,
    *,
    replacement_reasons: dict[tuple[str, str], str] | None = None,
) -> tuple[str, str, int, list[dict[str, Any]]]:
    """Validate a worksheet and produce a proposed JSONL merge in memory."""
    replacement_reasons = replacement_reasons or {}
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
    corrections: list[dict[str, Any]] = []
    used_replacements: set[tuple[str, str]] = set()
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
                field_path = f"oracle_facts.{target_field}"
                changed_fields += _merge_annotation_value(
                    facts,
                    target_field,
                    value,
                    gold_id=gold_id,
                    field_path=field_path,
                    reasons=replacement_reasons,
                    used_replacements=used_replacements,
                    corrections=corrections,
                )

        for field, raw in supplied_outcome.items():
            if raw:
                changed_fields += _merge_annotation_value(
                    record,
                    field,
                    raw,
                    gold_id=gold_id,
                    field_path=field,
                    reasons=replacement_reasons,
                    used_replacements=used_replacements,
                    corrections=corrections,
                )
        changed_fields += _append_note(record, annotation.get("notes") or "")
        validate_gold_record(record)

    unused_replacements = set(replacement_reasons) - used_replacements
    if unused_replacements:
        gold_id, field = sorted(unused_replacements)[0]
        raise ValueError(f"--replace {gold_id}:{field} did not change a supplied field")
    rendered = "".join(json.dumps(rows[gold_id], ensure_ascii=False) + "\n" for gold_id in order)
    return original, rendered, changed_fields, corrections


def _replacement_reasons(replacements: list[str], reasons: list[str]) -> dict[tuple[str, str], str]:
    """Parse paired --replace and --reason options, rejecting ambiguous input."""
    if len(replacements) != len(reasons):
        raise ValueError("each --replace requires one corresponding --reason")
    parsed: dict[tuple[str, str], str] = {}
    for item, reason in zip(replacements, reasons, strict=True):
        gold_id, separator, field = item.partition(":")
        if not separator or not gold_id or field not in REPLACE_FIELDS:
            raise ValueError(
                f"invalid replacement {item!r}; field must be one of {sorted(REPLACE_FIELDS)}"
            )
        key = (gold_id, field)
        if key in parsed:
            raise ValueError(f"duplicate replacement {item!r}")
        if not reason.strip():
            raise ValueError(f"replacement {item!r} requires a non-empty reason")
        parsed[key] = reason.strip()
    return parsed


def _append_corrections(path: Path, corrections: list[dict[str, Any]]) -> None:
    """Append explicit, reasoned replacements atomically to the JSONL ledger."""
    if not corrections:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    separator = "" if not existing or existing.endswith("\n") else "\n"
    additions = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in corrections)
    _atomic_write_text(path, existing + separator + additions)


def _atomic_write_text(path: Path, content: str) -> None:
    """Replace one file through a same-directory temporary file."""
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
    """Print a proposed unified diff; write only when --apply is supplied."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--gold-sheet", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--correction-ledger", type=Path, default=DEFAULT_CORRECTION_LEDGER)
    parser.add_argument(
        "--replace",
        action="append",
        default=[],
        metavar="GOLD_ID:FIELD",
        help="allow replacing one existing annotation field; requires a matching --reason",
    )
    parser.add_argument(
        "--reason",
        action="append",
        default=[],
        help="reason paired by order with each --replace",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write the validated merge (default is preview only)",
    )
    args = parser.parse_args(argv)

    try:
        replacement_reasons = _replacement_reasons(args.replace, args.reason)
        original, merged, changed_fields, corrections = prepare_import(
            args.csv, args.gold_sheet, replacement_reasons=replacement_reasons
        )
    except ValueError as error:
        parser.error(str(error))
    diff = difflib.unified_diff(
        original.splitlines(keepends=True),
        merged.splitlines(keepends=True),
        fromfile=str(args.gold_sheet),
        tofile=f"{args.gold_sheet} (proposed)",
    )
    diff_text = "".join(diff)
    print(diff_text or "No JSONL changes proposed.")
    print(f"Validated worksheet; {changed_fields} new field values.")
    for correction in corrections:
        print(
            "Correction: "
            f"{correction['gold_id']}.{correction['field']} "
            f"{correction['old_value']!r} → {correction['new_value']!r}; "
            f"reason: {correction['reason']}"
        )
    if args.apply:
        _atomic_write_text(args.gold_sheet, merged)
        _append_corrections(args.correction_ledger, corrections)
        print(f"Applied merge to {args.gold_sheet}.")
        if corrections:
            print(f"Appended correction ledger {args.correction_ledger}.")
    else:
        print("Preview only; pass --apply to write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
