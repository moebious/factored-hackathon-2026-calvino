"""Label definitions, proxy mapping and gold-record schema (TSD-015, T-103)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from calvino.data.labels import (
    BinaryLabel,
    GoldOracleFacts,
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


def test_existing_gold_sheet_rows_remain_valid_without_outcome_fields():
    """The additive report schema must preserve all current rows."""
    rows = [
        json.loads(line)
        for line in GOLD_SHEET.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 50
    records = [validate_gold_record(row) for row in rows]
    assert all(record.oracle_facts is None for record in records)
    assert all(record.human_outcome is None for record in records)
    assert all(not record.has_complete_outcome_annotation() for record in records)


def test_gold_outcome_fields_are_optional_but_require_complete_metadata_for_scoring():
    row = {
        "gold_id": "gold-test",
        "rubric_version": "v1",
        "message": "synthetic test-only message",
        "language_variant": "es-MX",
        "seed_ref": "hand-written",
        "labels": {},
        "oracle_facts": {
            "intent": "none",
            "ambiguous": True,
            "status": None,
            "owner": True,
            "amount_band": "under_gate",
            "fraud_flag": False,
            "in_scope": True,
        },
        "human_outcome": "clarify",
        "outcome_annotator": "maintainer",
        "outcome_labelled_at": "2026-10-04",
    }
    record = validate_gold_record(row)
    assert record.has_complete_outcome_annotation()
    assert record.oracle_facts is not None
    assert record.oracle_facts.status is None

    for field in ("outcome_annotator", "outcome_labelled_at"):
        partial = dict(row)
        partial[field] = ""
        assert field in validate_gold_record(partial).outcome_annotation_missing()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("intent", "refund"),
        ("amount_band", "near_gate"),
        ("status", "Approved"),
        ("human_outcome", "error"),
    ],
)
def test_gold_outcome_schema_rejects_unknown_or_error_values(field, value):
    row = {
        "gold_id": "gold-test",
        "rubric_version": "v1",
        "message": "synthetic test-only message",
        "language_variant": "es-MX",
        "seed_ref": "hand-written",
        "oracle_facts": {
            "intent": "none",
            "ambiguous": True,
            "status": None,
            "owner": True,
            "amount_band": "under_gate",
            "fraud_flag": False,
            "in_scope": True,
        },
        "human_outcome": "clarify",
        "outcome_annotator": "maintainer",
        "outcome_labelled_at": "2026-10-04",
    }
    if field in {"intent", "amount_band", "status"}:
        row["oracle_facts"][field] = value
    else:
        row[field] = value
    with pytest.raises(ValidationError):
        validate_gold_record(row)


def test_gold_oracle_facts_allow_drafts_but_reject_null_required_fields():
    draft = GoldOracleFacts(intent="none", status=None)
    assert draft.model_fields_set == {"intent", "status"}
    with pytest.raises(ValidationError, match="only status may be null"):
        GoldOracleFacts(intent=None)


def test_fraud_record_without_intent_counts_as_labelled():
    record = GoldRecord(
        gold_id="gold-002",
        rubric_version="v1",
        message="synthetic team-written message",
        language_variant="es-MX",
        seed_ref="hand-written",
        labels={
            "workflow_area": "fraud or stolen access",
            "stuck_intent": None,
            "clear_enough": "yes",
            "needs_person": "yes",
            "injection": "no",
        },
    )
    assert record.is_labelled()


def test_stuck_record_without_intent_counts_as_unlabelled():
    record = GoldRecord(
        gold_id="gold-003",
        rubric_version="v1",
        message="synthetic team-written message",
        language_variant="es-MX",
        seed_ref="hand-written",
        labels={
            "workflow_area": "stuck payment",
            "stuck_intent": None,
            "clear_enough": "yes",
            "needs_person": "no",
            "injection": "no",
        },
    )
    assert not record.is_labelled()


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
