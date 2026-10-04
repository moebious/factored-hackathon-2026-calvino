"""Label definitions, proxy mapping and gold-record schema (TSD-015, T-103)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from calvino.data.labels import (
    BinaryLabel,
    GoldRecord,
    StuckIntent,
    WorkflowArea,
    proxy_escalated,
    proxy_followup_needed,
    proxy_investigation_outcome,
    proxy_problem_transaction,
    proxy_resolved,
    validate_gold_record,
)

GOLD_SHEET = Path(__file__).resolve().parents[2] / "fixtures" / "gold" / "gold-050.jsonl"


def test_label_tables_match_the_spec():
    assert [a.value for a in WorkflowArea] == [
        "stuck payment",
        "dispute or unrecognised charge",
        "fraud or stolen access",
        "other banking",
        "out of scope",
    ]
    assert [i.value for i in StuckIntent] == [
        "status",
        "cancel",
        "retry",
        "open a case",
        "case status",
        "talk to a person",
    ]
    assert [b.value for b in BinaryLabel] == ["yes", "no"]


def test_proxy_mapping_on_fixture_rows():
    assert proxy_resolved({"was_resolved": True}) is True
    assert proxy_escalated({"was_escalated": False}) is False
    assert proxy_followup_needed({"requires_followup": True}) is True
    assert proxy_problem_transaction({"transaction_status": "Pending"}) is True
    assert proxy_problem_transaction({"transaction_status": "Approved"}) is False
    # Missing source columns give no proxy, never a guessed label.
    assert proxy_resolved({}) is None
    assert proxy_problem_transaction({}) is None


def test_proxy_investigation_outcome_carries_the_source_fields():
    outcome = proxy_investigation_outcome(
        {
            "status": "Closed",
            "sla_breached": False,
            "resolution_days": 3.0,
            "compensation_granted": None,
        }
    )
    assert outcome == {
        "status": "Closed",
        "sla_breached": False,
        "resolution_days": 3.0,
        "compensation_granted": None,
    }


def test_empty_sheet_record_validates_and_counts_as_unlabelled():
    record = validate_gold_record(
        {
            "gold_id": "gold-001",
            "rubric_version": "v1",
            "message": "synthetic team-written message",
            "language_variant": "es-MX",
            "seed_ref": "hand-written",
            "labels": {},
            "annotator": "",
            "labelled_at": "",
            "notes": "stratum status/es-MX",
        }
    )
    assert not record.is_labelled()


def test_filled_record_counts_as_labelled():
    record = GoldRecord(
        gold_id="gold-001",
        rubric_version="v1",
        message="synthetic team-written message",
        language_variant="es-MX",
        seed_ref="hand-written",
        labels={
            "workflow_area": "stuck payment",
            "stuck_intent": "status",
            "clear_enough": "yes",
            "needs_person": "no",
            "injection": "no",
        },
    )
    assert record.is_labelled()


def test_gold_record_rejects_unknown_label_values():
    with pytest.raises(ValueError):
        validate_gold_record(
            {
                "gold_id": "gold-001",
                "rubric_version": "v1",
                "message": "synthetic team-written message",
                "language_variant": "es-MX",
                "seed_ref": "hand-written",
                "labels": {"workflow_area": "refunds"},
            }
        )


def _normalise(text: str) -> str:
    return re.sub(r"\d", "#", text.strip().lower())


def test_gold_sheet_messages_are_not_templated_repetitions():
    """Necessary condition of non-templatedness: no two sheet messages share
    a digit-masked, lowercased shape (dataset templates repeat verbatim)."""
    if not GOLD_SHEET.exists():
        pytest.skip("gold sheet lands in a later commit")
    shapes = [
        _normalise(json.loads(line)["message"])
        for line in GOLD_SHEET.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(shapes) == 50
    assert len(set(shapes)) == len(shapes)
