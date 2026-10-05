"""Tests for the T-107 gold/oracle consistency report.

Fixtures are synthetic, maintainer-entered examples; this module never
proposes or writes values into the committed gold sheet.
"""

from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

import pytest

from calvino.data.labels import GoldRecord, validate_gold_record

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "report_gold_agreement.py"
SPEC = importlib.util.spec_from_file_location("report_gold_agreement", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
report = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = report
SPEC.loader.exec_module(report)

GOLD_SHEET = ROOT / "tests" / "fixtures" / "gold" / "gold-050.jsonl"


def _gold_row(
    gold_id: str,
    *,
    intent: str | None = None,
    ambiguous: bool | None = None,
    status: str | None = None,
    owner: bool | None = None,
    amount_band: str | None = None,
    fraud_flag: bool | None = None,
    in_scope: bool | None = None,
    human_outcome: str | None = None,
) -> GoldRecord:
    """Build an in-memory test row without modifying committed labels."""
    data = {
        "gold_id": gold_id,
        "rubric_version": "v1",
        "message": "synthetic test-only message",
        "language_variant": "es-MX",
        "seed_ref": "hand-written",
        "labels": {},
    }
    oracle_values = {
        "intent": intent,
        "ambiguous": ambiguous,
        "status": status,
        "owner": owner,
        "amount_band": amount_band,
        "fraud_flag": fraud_flag,
        "in_scope": in_scope,
    }
    if any(value is not None for key, value in oracle_values.items() if key != "status") or (
        intent is not None
    ):
        data["oracle_facts"] = oracle_values
    if human_outcome is not None:
        data.update(
            human_outcome=human_outcome,
            outcome_annotator="maintainer-test",
            outcome_labelled_at="2026-10-04",
        )
    return validate_gold_record(data)


def test_existing_fifty_rows_load_and_are_reported_unscored():
    rows = report.load_gold_sheet(GOLD_SHEET)
    assert len(rows) == 50
    assert all(row.record is not None for row in rows)
    assert all(not row.record.has_complete_outcome_annotation() for row in rows if row.record)
    body = report.render_report(rows, run_date="2026-10-04", git_sha="test")
    assert body.startswith("# T-107 gold/oracle consistency report")
    assert "scored 0/50" in body
    assert "gold-001" in body
    assert "oracle_facts, human_outcome, outcome_annotator, outcome_labelled_at" in body


def test_loader_keeps_invalid_rows_in_unscored_denominator(tmp_path):
    path = tmp_path / "gold.jsonl"
    path.write_text(
        """{"gold_id":"bad-row","unexpected":"extra"}
{"gold_id":"broken-json"
""",
        encoding="utf-8",
    )
    rows = report.load_gold_sheet(path)
    assert len(rows) == 2
    body = report.render_report(rows, run_date="2026-10-04", git_sha="test")
    assert "Gold sheet: 2 rows; scored 0/2" in body
    assert "bad-row" in body and "schema validation failed" in body
    assert "line-2" in body and "invalid JSON" in body


def test_blank_template_orders_raw_facts_before_judgements_and_never_fills_values(tmp_path):
    rows = [row.record for row in report.load_gold_sheet(GOLD_SHEET)[:2] if row.record is not None]
    target = tmp_path / "annotations.csv"
    report.write_blank_annotation_template(rows, target)
    with target.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        columns = reader.fieldnames
        annotated = list(reader)

    assert columns is not None
    assert columns.index("record_status") < columns.index("oracle_intent")
    assert columns.index("fraud_flag") < columns.index("oracle_in_scope")
    assert columns.index("oracle_in_scope") < columns.index("human_outcome")
    assert not {"workflow_area", "stuck_intent", "clear_enough", "needs_person", "injection"} & set(
        columns
    )
    assert [row["gold_id"] for row in annotated] == ["gold-001", "gold-002"]
    for row in annotated:
        assert row["message"]
        assert all(row[column] == "" for column in report.ANNOTATION_COLUMNS)


def test_blank_template_refuses_to_overwrite_a_maintainer_sheet(tmp_path):
    target = tmp_path / "annotations.csv"
    target.write_text("maintainer work\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        report.write_blank_annotation_template(report.load_gold_sheet(GOLD_SHEET)[:1], target)
    assert target.read_text(encoding="utf-8") == "maintainer work\n"


def test_committed_annotation_sheet_has_all_fifty_rows_and_no_suggestions():
    template = ROOT / "docs" / "templates" / "T-103-gold-outcome-annotations.csv"
    with template.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        rows = list(reader)
    assert len(rows) == 50
    assert [row["gold_id"] for row in rows] == [f"gold-{index:03d}" for index in range(1, 51)]
    assert all(row[column] == "" for row in rows for column in report.ANNOTATION_COLUMNS)


def test_cli_writes_report_and_blank_template_to_requested_paths(tmp_path, capsys):
    template = tmp_path / "annotations.csv"
    output = tmp_path / "agreement.md"
    disagreements = tmp_path / "disagreements.md"
    result = report.main(
        [
            "--run-date",
            "2026-10-04",
            "--git-sha",
            "test",
            "--gold-sheet",
            str(GOLD_SHEET),
            "--write-template",
            str(template),
            "--report",
            str(output),
            "--disagreements",
            str(disagreements),
        ]
    )
    assert result == 0
    assert "scored 0/50" in capsys.readouterr().out
    assert "scored 0/50" in output.read_text(encoding="utf-8")
    assert template.exists()
    assert disagreements.exists()


def test_report_states_scored_denominator_and_unscored_reasons():
    reviewed = _gold_row(
        "gold-test-001",
        intent="none",
        ambiguous=True,
        owner=True,
        amount_band="under_gate",
        fraud_flag=False,
        in_scope=True,
        human_outcome="clarify",
    )
    incomplete = _gold_row("gold-test-002")
    body = report.render_report((reviewed, incomplete), run_date="2026-10-04", git_sha="test")
    assert "scored 1/2" in body
    assert "| Oracle outcome equals maintainer outcome | 1 | 1 | 100.0% |" in body
    assert "- Outcome annotator: maintainer-test" in body
    assert "Cohen's kappa: not defined" in body
    assert (
        "| gold-test-002 | oracle_facts, human_outcome, outcome_annotator, outcome_labelled_at |"
    ) in body
    assert "single-annotator" in body
    assert "real-world oracle error bound" in body


def test_report_rejects_multiple_outcome_annotators():
    record = _gold_row(
        "gold-test-004",
        intent="none",
        ambiguous=True,
        owner=True,
        amount_band="under_gate",
        fraud_flag=False,
        in_scope=True,
        human_outcome="clarify",
    )
    other = record.model_copy(update={"outcome_annotator": "other-reviewer"})
    with pytest.raises(ValueError, match="requires one outcome annotator"):
        report.render_report((record, other), run_date="2026-10-04", git_sha="test")


def test_disagreement_ledger_adds_pending_rows_and_preserves_maintainer_resolution(tmp_path):
    disagreeing = _gold_row(
        "gold-test-003",
        intent="explain",
        ambiguous=False,
        status="Pending",
        owner=True,
        amount_band="under_gate",
        fraud_flag=False,
        in_scope=True,
        human_outcome="clarify",
    )
    scored = report._scored_outcomes((disagreeing,))
    path = tmp_path / "disagreements.md"
    report.update_disagreement_log(scored, path)
    original = path.read_text(encoding="utf-8")
    pending = (
        "| gold-test-003 | explain | clarify | pending | pending | pending | pending | pending |"
    )
    resolved = (
        "| gold-test-003 | explain | clarify | rubric gap | reason | "
        "documented | maintainer | 2026-10-04 |"
    )
    assert pending in original

    path.write_text(
        original.replace(pending, resolved),
        encoding="utf-8",
    )
    report.update_disagreement_log(scored, path)
    resolved = path.read_text(encoding="utf-8")
    assert "rubric gap" in resolved
    assert resolved.count("gold-test-003") == 1
