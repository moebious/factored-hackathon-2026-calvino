"""Classifier labels, proxy mapping and gold-record validation (TSD-015, T-103).

The labels follow Laya's questions in DESIGN 6.1; this module is the rubric's
single source. Proxy fields show what agents *did*, not what was *needed*,
so they feed the human baseline only, never classifier targets.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from pydantic import BaseModel, Field, StrictBool, field_validator, model_validator

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
    """One gold case's classifier labels; unset fields remain unlabelled."""

    model_config = {"extra": "forbid"}

    workflow_area: WorkflowArea | None = None
    stuck_intent: StuckIntent | None = None
    clear_enough: BinaryLabel | None = None
    needs_person: BinaryLabel | None = None
    injection: BinaryLabel | None = None


class GoldOracleFacts(BaseModel):
    """Maintainer-entered TSD-013 facts for the T-103 consistency report.

    These are nominal scenario facts for hand-written gold messages, not
    claims about real bank records. Missing facts are never inferred.
    """

    model_config = {"extra": "forbid"}

    intent: str | None = None
    ambiguous: StrictBool | None = None
    status: str | None = None
    owner: StrictBool | None = None
    amount_band: str | None = None
    fraud_flag: StrictBool | None = None
    in_scope: StrictBool | None = None

    @field_validator("intent")
    @classmethod
    def intent_is_in_oracle_table(cls, value: str | None) -> str | None:
        """Keep the gold sheet aligned with TSD-013's frozen intent set."""
        from calvino.evaluation.oracle import INTENTS

        if value is not None and value not in INTENTS:
            raise ValueError(f"unknown TSD-013 intent {value!r}")
        return value

    @field_validator("amount_band")
    @classmethod
    def amount_band_is_in_oracle_table(cls, value: str | None) -> str | None:
        """Keep the gold sheet aligned with TSD-013's frozen amount bands."""
        from calvino.evaluation.oracle import AMOUNT_BANDS

        if value is not None and value not in AMOUNT_BANDS:
            raise ValueError(f"unknown TSD-013 amount band {value!r}")
        return value

    @field_validator("status")
    @classmethod
    def status_is_nullable_problem_status(cls, value: str | None) -> str | None:
        """Allow only the transaction statuses represented by the oracle."""
        if value is not None and value not in PROBLEM_TRANSACTION_STATUSES:
            raise ValueError(f"unknown TSD-013 transaction status {value!r}")
        return value

    @model_validator(mode="after")
    def required_supplied_facts_cannot_be_null(self) -> GoldOracleFacts:
        """Allow omitted draft fields but permit null only for status."""
        required = {
            "intent",
            "ambiguous",
            "owner",
            "amount_band",
            "fraud_flag",
            "in_scope",
        }
        invalid_nulls = sorted(
            field for field in required & self.model_fields_set if getattr(self, field) is None
        )
        if invalid_nulls:
            raise ValueError(
                "only status may be null; invalid null fields: " + ", ".join(invalid_nulls)
            )
        return self


class GoldRecord(BaseModel):
    """One team-generated gold message and optional maintainer annotations.

    Nominal oracle facts describe the scenario, never a customer record.
    """

    model_config = {"extra": "forbid"}

    gold_id: str = Field(min_length=1)
    rubric_version: str = Field(min_length=1)
    message: str = Field(min_length=1)
    language_variant: str
    seed_ref: str = Field(min_length=1)
    labels: GoldLabels = Field(default_factory=GoldLabels)
    oracle_facts: GoldOracleFacts | None = None
    human_outcome: str | None = None
    outcome_annotator: str | None = None
    outcome_labelled_at: str | None = None
    annotator: str = ""
    labelled_at: str = ""
    notes: str = ""

    @field_validator("human_outcome")
    @classmethod
    def outcome_is_produced_by_oracle_table(cls, value: str | None) -> str | None:
        """Accept only TSD-013 outcomes the table can actually produce."""
        if value is None:
            return None
        from calvino.evaluation.oracle import ExpectedOutcome

        if value not in {outcome.value for outcome in ExpectedOutcome if outcome.value != "error"}:
            raise ValueError(f"unknown TSD-013 non-error outcome {value!r}")
        return value

    def outcome_annotation_missing(self) -> tuple[str, ...]:
        """Fields missing before this row can enter the T-103 comparison."""
        missing = []
        if self.oracle_facts is None:
            missing.append("oracle_facts")
        else:
            for field in (
                "intent",
                "ambiguous",
                "status",
                "owner",
                "amount_band",
                "fraud_flag",
                "in_scope",
            ):
                if field not in self.oracle_facts.model_fields_set or (
                    field != "status" and getattr(self.oracle_facts, field) is None
                ):
                    missing.append(f"oracle_facts.{field}")
        if self.human_outcome is None:
            missing.append("human_outcome")
        if not self.outcome_annotator:
            missing.append("outcome_annotator")
        if not self.outcome_labelled_at:
            missing.append("outcome_labelled_at")
        return tuple(missing)

    def has_complete_outcome_annotation(self) -> bool:
        """Whether every separately reviewed outcome field is present."""
        return not self.outcome_annotation_missing()

    def is_labelled(self) -> bool:
        """Whether the maintainer has filled every applicable label column.

        stuck_intent applies only to stuck-payment records; every other
        workflow area leaves it empty by rubric, never guessed.
        """
        if (
            self.labels.workflow_area is None
            or self.labels.clear_enough is None
            or self.labels.needs_person is None
            or self.labels.injection is None
        ):
            return False
        if self.labels.workflow_area == WorkflowArea.STUCK_PAYMENT:
            return self.labels.stuck_intent is not None
        return True


def validate_gold_record(data: dict) -> GoldRecord:
    """Parse and validate one gold JSONL row, raising on schema violations."""
    return GoldRecord.model_validate(data)
