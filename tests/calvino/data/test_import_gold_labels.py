"""Tests for the preview-first T-107 classifier-label importer."""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "import_gold_labels.py"
SPEC = importlib.util.spec_from_file_location("import_gold_labels", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
importer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = importer
SPEC.loader.exec_module(importer)


def _files(tmp_path: Path, *, existing_labels: dict | None = None):
    """Create one synthetic gold row and a matching annotation worksheet."""
    record = {
        "gold_id": "gold-test-001",
        "rubric_version": "v1",
        "message": "¿Dónde está mi pago?",
        "language_variant": "es-MX",
        "seed_ref": "hand-written",
        "labels": existing_labels or {},
        "annotator": "maintainer" if existing_labels else "",
        "labelled_at": "2026-10-05" if existing_labels else "",
    }
    gold = tmp_path / "gold.jsonl"
    gold.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")

    worksheet = tmp_path / "labels.csv"
    row = {field: "" for field in importer.CSV_FIELDS}
    row.update(
        gold_id=record["gold_id"],
        message=record["message"],
        language_variant=record["language_variant"],
        workflow_area="stuck payment",
        stuck_intent="status",
        clear_enough="yes",
        needs_person="no",
        injection="no",
        annotator="maintainer",
        labelled_at="2026-10-05",
    )
    with worksheet.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=importer.CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerow(row)
    return gold, worksheet, record


def test_preview_does_not_write_and_apply_merges_only_missing_labels(tmp_path, capsys):
    existing = {"workflow_area": "stuck payment", "stuck_intent": "status"}
    gold, worksheet, record = _files(tmp_path, existing_labels=existing)
    original = gold.read_text(encoding="utf-8")

    assert importer.main(["--csv", str(worksheet), "--gold-sheet", str(gold)]) == 0
    assert "Preview only" in capsys.readouterr().out
    assert gold.read_text(encoding="utf-8") == original

    assert importer.main(["--csv", str(worksheet), "--gold-sheet", str(gold), "--apply"]) == 0
    assert "Applied merge" in capsys.readouterr().out
    merged = json.loads(gold.read_text(encoding="utf-8"))
    assert merged["labels"] == {
        "workflow_area": "stuck payment",
        "stuck_intent": "status",
        "clear_enough": "yes",
        "needs_person": "no",
        "injection": "no",
    }
    assert merged["annotator"] == record["annotator"]
    assert merged["labelled_at"] == record["labelled_at"]


def test_import_refuses_conflicting_existing_label(tmp_path):
    existing = {"workflow_area": "stuck payment", "stuck_intent": "retry"}
    gold, worksheet, _ = _files(tmp_path, existing_labels=existing)
    original = gold.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="refusing to replace"):
        importer.prepare_import(worksheet, gold)
    assert gold.read_text(encoding="utf-8") == original


def test_import_rejects_invalid_labels_without_writing(tmp_path):
    gold, worksheet, _ = _files(tmp_path)
    rows = list(csv.DictReader(worksheet.open(encoding="utf-8", newline="")))
    rows[0]["clear_enough"] = "maybe"
    with worksheet.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=importer.CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    original = gold.read_text(encoding="utf-8")

    with pytest.raises(ValueError):
        importer.prepare_import(worksheet, gold)
    assert gold.read_text(encoding="utf-8") == original


def test_import_requires_annotator_and_date_for_labels(tmp_path):
    gold, worksheet, _ = _files(tmp_path)
    rows = list(csv.DictReader(worksheet.open(encoding="utf-8", newline="")))
    rows[0]["annotator"] = ""
    with worksheet.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=importer.CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    with pytest.raises(ValueError, match="require annotator and labelled_at"):
        importer.prepare_import(worksheet, gold)


def test_import_rejects_changed_message_identity(tmp_path):
    gold, worksheet, _ = _files(tmp_path)
    rows = list(csv.DictReader(worksheet.open(encoding="utf-8", newline="")))
    rows[0]["message"] = "different message"
    with worksheet.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=importer.CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    with pytest.raises(ValueError, match="worksheet message does not match"):
        importer.prepare_import(worksheet, gold)


def test_template_contains_all_rows_and_preserves_existing_labels():
    template = ROOT / "docs" / "templates" / "T-107-gold-classifier-labels.csv"
    with template.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    assert len(rows) == 50
    assert [row["gold_id"] for row in rows] == [f"gold-{n:03d}" for n in range(1, 51)]
    assert sum(bool(row["annotator"]) for row in rows) == 18
    assert rows[0]["workflow_area"] == "stuck payment"
    assert rows[1]["workflow_area"] == ""
    assert rows[1]["clear_enough"] == ""

    gold = ROOT / "tests" / "fixtures" / "gold" / "gold-050.jsonl"
    original = gold.read_text(encoding="utf-8")
    before, proposed, changed, complete = importer.prepare_import(template, gold)
    assert before == original == proposed
    assert changed == 0
    assert complete == 18


def test_default_csv_is_an_ignored_working_copy():
    assert importer.DEFAULT_CSV == ROOT / "data" / "T-107-gold-classifier-labels.csv"
    assert importer.DEFAULT_CSV != importer.DEFAULT_TEMPLATE
