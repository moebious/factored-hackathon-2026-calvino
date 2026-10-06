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


def test_existing_gold_sheet_rows_remain_valid_with_outcome_fields():
    """The reviewed gold rows validate under the additive report schema."""
    rows = [
        json.loads(line)
        for line in GOLD_SHEET.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 50
    records = [validate_gold_record(row) for row in rows]
    assert all(record.oracle_facts is not None for record in records)
    assert all(record.human_outcome is not None for record in records)
    assert all(record.has_complete_outcome_annotation() for record in records)


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
        ("status", "Succeeded"),
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


def test_gold_outcome_schema_accepts_approved_clean_transaction():
    from calvino.evaluation.oracle import OracleFacts, oracle_outcome

    facts = GoldOracleFacts(
        intent="cancel",
        ambiguous=False,
        status="Approved",
        owner=True,
        amount_band="under_gate",
        fraud_flag=False,
        in_scope=True,
    )
    assert facts.status == "Approved"
    assert oracle_outcome(OracleFacts(**facts.model_dump())).value == "act_block"


@pytest.mark.parametrize(
    "value",
    ["10/05/2026", "2026-2-5", "2026-10-05T00:00:00", "2026-02-30"],
)
def test_gold_outcome_date_rejects_non_iso_or_invalid_dates(value):
    with pytest.raises(ValidationError, match="ISO date"):
        GoldRecord(
            gold_id="gold-date-test",
            rubric_version="v1",
            message="synthetic test-only message",
            language_variant="es-MX",
            seed_ref="hand-written",
            outcome_labelled_at=value,
        )


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


def test_unclassifiable_record_without_area_counts_as_labelled_when_unclear():
    record = GoldRecord(
        gold_id="gold-039",
        rubric_version="v1",
        message="...",
        language_variant="es-MX",
        seed_ref="hand-written",
        oracle_facts={"intent": "none"},
        labels={
            "workflow_area": None,
            "stuck_intent": None,
            "clear_enough": "no",
            "needs_person": "no",
            "injection": "no",
        },
    )
    assert record.is_labelled()


def test_unset_area_with_non_none_or_missing_oracle_intent_is_incomplete():
    base = {
        "gold_id": "gold-area-unset",
        "rubric_version": "v1",
        "message": "...",
        "language_variant": "es-MX",
        "seed_ref": "hand-written",
        "labels": {
            "workflow_area": None,
            "stuck_intent": None,
            "clear_enough": "no",
            "needs_person": "no",
            "injection": "no",
        },
    }
    assert not GoldRecord(**base).is_labelled()
    assert not GoldRecord(**base, oracle_facts={"intent": "explain"}).is_labelled()


def test_missing_area_does_not_count_as_labelled_when_message_is_clear():
    record = GoldRecord(
        gold_id="gold-clear-without-area",
        rubric_version="v1",
        message="synthetic clear message",
        language_variant="es-MX",
        seed_ref="hand-written",
        labels={
            "workflow_area": None,
            "stuck_intent": None,
            "clear_enough": "yes",
            "needs_person": "no",
            "injection": "no",
        },
    )
    assert not record.is_labelled()


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
