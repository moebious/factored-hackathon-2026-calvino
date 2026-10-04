"""Classifier labels, proxy mapping and gold-record validation (TSD-015, T-103).

The labels follow Laya's questions in DESIGN 6.1; this module is the rubric's
single source. Proxy fields show what agents *did*, not what was *needed*,
so they feed the human baseline only, never classifier targets.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from pydantic import BaseModel, Field

RUBRIC_VERSION = "v1"

PROBLEM_TRANSACTION_STATUSES = ("Declined", "Pending", "Reversed")


class WorkflowArea(StrEnum):
    """Which workflow area a customer message belongs to."""

    STUCK_PAYMENT = "stuck payment"
    DISPUTE = "dispute or unrecognised charge"
    FRAUD = "fraud or stolen access"
    OTHER_BANKING = "other banking"
    OUT_OF_SCOPE = "out of scope"


class StuckIntent(StrEnum):
    """What the customer wants done about a stuck payment."""

    STATUS = "status"
    CANCEL = "cancel"
    RETRY = "retry"
    OPEN_CASE = "open a case"
    CASE_STATUS = "case status"
    TALK_TO_PERSON = "talk to a person"


class BinaryLabel(StrEnum):
    """Two-option answers. Prompts use neutral keys (never yes/no, DESIGN 4.3
    rule 5); the oracle maps those keys back onto yes/no for the gold sheet."""

    YES = "yes"
    NO = "no"


def proxy_resolved(row: Mapping[str, object]) -> bool | None:
    """Proxy for Resolved from ``call_center_interactions.was_resolved``."""
    value = row.get("was_resolved")
    return None if value is None else bool(value)


def proxy_escalated(row: Mapping[str, object]) -> bool | None:
    """Proxy for Escalated from ``call_center_interactions.was_escalated``."""
    value = row.get("was_escalated")
    return None if value is None else bool(value)


def proxy_followup_needed(row: Mapping[str, object]) -> bool | None:
    """Proxy for Follow-up needed from ``requires_followup``."""
    value = row.get("requires_followup")
    return None if value is None else bool(value)


def proxy_problem_transaction(row: Mapping[str, object]) -> bool | None:
    """Proxy for Problem transaction from ``transaction_status``."""
    status = row.get("transaction_status")
    if status is None:
        return None
    return status in PROBLEM_TRANSACTION_STATUSES


def proxy_investigation_outcome(row: Mapping[str, object]) -> dict[str, object | None]:
    """Proxy outcome fields from a complaints row, for the baseline only."""
    return {
        "status": row.get("status"),
        "sla_breached": row.get("sla_breached"),
        "resolution_days": row.get("resolution_days"),
        "compensation_granted": row.get("compensation_granted"),
    }


class GoldLabels(BaseModel):
    """One gold case's labels. All optional: the empty labelling sheet ships
    with every column unfilled for the maintainer to label by hand."""

    model_config = {"extra": "forbid"}

    workflow_area: WorkflowArea | None = None
    stuck_intent: StuckIntent | None = None
    clear_enough: BinaryLabel | None = None
    needs_person: BinaryLabel | None = None
    injection: BinaryLabel | None = None


class GoldRecord(BaseModel):
    """One row of ``tests/fixtures/gold/gold-050.jsonl``: team-generated
    message plus seed facts, never a customer record or dataset text."""

    model_config = {"extra": "forbid"}

    gold_id: str = Field(min_length=1)
    rubric_version: str = Field(min_length=1)
    message: str = Field(min_length=1)
    language_variant: str
    seed_ref: str = Field(min_length=1)
    labels: GoldLabels = Field(default_factory=GoldLabels)
    annotator: str = ""
    labelled_at: str = ""
    notes: str = ""

    def is_labelled(self) -> bool:
        """Whether the maintainer has filled every label column."""
        return all(
            value is not None
            for value in (
                self.labels.workflow_area,
                self.labels.stuck_intent,
                self.labels.clear_enough,
                self.labels.needs_person,
                self.labels.injection,
            )
        )


def validate_gold_record(data: dict) -> GoldRecord:
    """Parse and validate one gold JSONL row, raising on schema violations."""
    return GoldRecord.model_validate(data)
