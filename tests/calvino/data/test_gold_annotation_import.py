"""Tests for safe T-103 annotation worksheet import."""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "import_gold_annotations.py"
SPEC = importlib.util.spec_from_file_location("import_gold_annotations", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
importer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = importer
SPEC.loader.exec_module(importer)


def _files(tmp_path: Path, *, status: str | None = None, human_outcome: str | None = None):
    """Build one synthetic source record and one worksheet row."""
    gold = tmp_path / "gold.jsonl"
    record = {
        "gold_id": "gold-test-001",
        "rubric_version": "v1",
        "message": "¿Dónde está mi pago?",
        "language_variant": "es-MX",
        "seed_ref": "hand-written",
        "labels": {
            "workflow_area": "stuck payment",
            "stuck_intent": "status",
            "clear_enough": "yes",
            "needs_person": "no",
            "injection": "no",
        },
    }
    if status is not None:
        record["oracle_facts"] = {
            "intent": "cancel",
            "ambiguous": False,
            "status": status,
            "owner": True,
            "amount_band": "under_gate",
            "fraud_flag": False,
            "in_scope": True,
        }
    gold.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")

    worksheet = tmp_path / "annotations.csv"
    row = {field: "" for field in importer.CSV_FIELDS}
    row.update(
        gold_id=record["gold_id"],
        message=record["message"],
        language_variant=record["language_variant"],
        record_status="Approved",
        owner="true",
        amount_band="under_gate",
        fraud_flag="false",
        oracle_intent="cancel",
        oracle_ambiguous="false",
        oracle_in_scope="true",
    )
    if human_outcome is not None:
        row.update(
            human_outcome=human_outcome,
            outcome_annotator="maintainer",
            outcome_labelled_at="2026-10-05",
        )
    with worksheet.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=importer.CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerow(row)
    return gold, worksheet, record


def test_preview_is_read_only_and_apply_merges_outcomes_but_preserves_labels(tmp_path, capsys):
    gold, worksheet, original = _files(tmp_path, human_outcome="act_block")
    original_text = gold.read_text(encoding="utf-8")

    assert importer.main(["--csv", str(worksheet), "--gold-sheet", str(gold)]) == 0
    preview = capsys.readouterr().out
    assert '"status": "Approved"' in preview
    assert "Preview only" in preview
    assert gold.read_text(encoding="utf-8") == original_text

    assert importer.main(["--csv", str(worksheet), "--gold-sheet", str(gold), "--apply"]) == 0
    assert "Applied merge" in capsys.readouterr().out
    merged = json.loads(gold.read_text(encoding="utf-8"))
    assert merged["labels"] == original["labels"]
    assert merged["oracle_facts"]["status"] == "Approved"
    assert merged["human_outcome"] == "act_block"
    assert merged["outcome_annotator"] == "maintainer"


def test_import_refuses_to_overwrite_existing_fact_and_keeps_source_unchanged(tmp_path):
    gold, worksheet, _ = _files(tmp_path, status="Pending")
    original_text = gold.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="refusing to replace"):
        importer.prepare_import(worksheet, gold)
    assert gold.read_text(encoding="utf-8") == original_text


def test_import_rejects_invalid_outcome_without_writing(tmp_path):
    gold, worksheet, _ = _files(tmp_path, human_outcome="error")
    original_text = gold.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="non-error outcome"):
        importer.prepare_import(worksheet, gold)
    assert gold.read_text(encoding="utf-8") == original_text


def test_import_contract_excludes_classifier_label_columns(tmp_path):
    gold, worksheet, _ = _files(tmp_path)
    with worksheet.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        assert reader.fieldnames == list(importer.CSV_FIELDS)
        assert not {"workflow_area", "stuck_intent", "needs_person"} & set(reader.fieldnames or ())
    assert importer.prepare_import(worksheet, gold)[2] > 0
