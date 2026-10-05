"""Tests for safe T-103 annotation worksheet import."""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
import unicodedata
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "import_gold_annotations.py"
SPEC = importlib.util.spec_from_file_location("import_gold_annotations", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
importer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = importer
SPEC.loader.exec_module(importer)


def _files(
    tmp_path: Path,
    *,
    status: str | None = None,
    human_outcome: str | None = None,
    csv_encoding: str = "utf-8",
):
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
    with worksheet.open("w", encoding=csv_encoding, newline="") as destination:
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


def test_import_rejects_invalid_outcome_date_without_writing(tmp_path):
    gold, worksheet, _ = _files(tmp_path, human_outcome="act_block")
    rows = list(csv.DictReader(worksheet.open(encoding="utf-8", newline="")))
    rows[0]["outcome_labelled_at"] = "10/05/2026"
    with worksheet.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=importer.CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    original_text = gold.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="ISO date"):
        importer.prepare_import(worksheet, gold)
    assert gold.read_text(encoding="utf-8") == original_text


def test_import_contract_excludes_classifier_label_columns(tmp_path):
    gold, worksheet, _ = _files(tmp_path)
    with worksheet.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        assert reader.fieldnames == list(importer.CSV_FIELDS)
        assert not {"workflow_area", "stuck_intent", "needs_person"} & set(reader.fieldnames or ())
    assert importer.prepare_import(worksheet, gold)[2] > 0


def test_default_csv_uses_ignored_working_copy_not_committed_template():
    committed_template = ROOT / "docs" / "templates" / "T-103-gold-outcome-annotations.csv"
    assert importer.DEFAULT_CSV == ROOT / "data" / "T-103-gold-outcome-annotations.csv"
    assert importer.DEFAULT_CSV != committed_template


def test_import_accepts_utf8_bom_csv(tmp_path):
    gold, worksheet, _ = _files(tmp_path, csv_encoding="utf-8-sig")
    assert importer.prepare_import(worksheet, gold)[2] > 0


def test_import_identity_uses_nfc_and_trimming(tmp_path):
    gold, worksheet, original = _files(tmp_path)
    rows = list(csv.DictReader(worksheet.open(encoding="utf-8", newline="")))
    rows[0]["message"] = f"  {unicodedata.normalize('NFD', original['message'])}  "
    rows[0]["language_variant"] = " es-MX "
    with worksheet.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=importer.CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    assert importer.prepare_import(worksheet, gold)[2] > 0


def test_import_rejects_real_message_identity_difference(tmp_path):
    gold, worksheet, _ = _files(tmp_path)
    rows = list(csv.DictReader(worksheet.open(encoding="utf-8", newline="")))
    rows[0]["message"] = "A different synthetic message"
    with worksheet.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=importer.CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    with pytest.raises(ValueError, match="worksheet message does not match"):
        importer.prepare_import(worksheet, gold)


def test_import_appends_notes_and_repeat_import_is_idempotent(tmp_path):
    gold, worksheet, _ = _files(tmp_path)
    rows = list(csv.DictReader(worksheet.open(encoding="utf-8", newline="")))
    rows[0]["notes"] = "Reviewed as an empty record."
    with worksheet.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=importer.CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    original, merged, count, corrections = importer.prepare_import(worksheet, gold)
    assert count > 0
    assert corrections == []
    assert json.loads(merged)["notes"] == "Reviewed as an empty record."
    assert gold.read_text(encoding="utf-8") == original

    gold.write_text(merged, encoding="utf-8")
    repeated_original, repeated_merged, repeated_count, _ = importer.prepare_import(worksheet, gold)
    assert repeated_count == 0
    assert repeated_merged == repeated_original


def test_explicit_replacement_requires_reason_and_appends_correction_ledger(tmp_path, capsys):
    gold, worksheet, _ = _files(tmp_path, status="Pending")
    replacement = ("gold-test-001", "oracle_facts.status")
    reason = "Maintainer rechecked the canonical scenario status."
    ledger = tmp_path / "corrections.jsonl"

    with pytest.raises(ValueError, match="refusing to replace"):
        importer.prepare_import(worksheet, gold)

    args = [
        "--csv",
        str(worksheet),
        "--gold-sheet",
        str(gold),
        "--correction-ledger",
        str(ledger),
        "--replace",
        ":".join(replacement),
        "--reason",
        reason,
        "--apply",
    ]
    assert importer.main(args) == 0
    output = capsys.readouterr().out
    assert "Correction: gold-test-001.oracle_facts.status" in output
    correction = json.loads(ledger.read_text(encoding="utf-8"))
    assert correction["gold_id"] == "gold-test-001"
    assert correction["field"] == "oracle_facts.status"
    assert correction["old_value"] == "Pending"
    assert correction["new_value"] == "Approved"
    assert correction["reason"] == reason
    assert json.loads(gold.read_text(encoding="utf-8"))["oracle_facts"]["status"] == "Approved"


def test_replace_argument_requires_matching_reason_and_valid_field():
    with pytest.raises(ValueError, match="one corresponding --reason"):
        importer._replacement_reasons(["gold-001:human_outcome"], [])
    with pytest.raises(ValueError, match="invalid replacement"):
        importer._replacement_reasons(["gold-001:labels.workflow_area"], ["reason"])


def test_failed_atomic_replace_preserves_original_gold_file(tmp_path, monkeypatch):
    gold, worksheet, _ = _files(tmp_path, human_outcome="act_block")
    original = gold.read_text(encoding="utf-8")

    def fail_replace(source, destination):
        raise OSError("simulated rename failure")

    monkeypatch.setattr(importer.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated rename failure"):
        importer.main(["--csv", str(worksheet), "--gold-sheet", str(gold), "--apply"])

    assert gold.read_text(encoding="utf-8") == original
    assert list(tmp_path.glob(".gold.jsonl.*.tmp")) == []
