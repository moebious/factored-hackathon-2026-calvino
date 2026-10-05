"""Typed inputs of the policy functions: Laya's calibrated scores, session facts and the action
the Gate is asked about.

Models are strict and forbid unknown fields, so a malformed input fails validation and the
caller fails closed. In particular ``act_probability`` is not a field: it carries no signal and
must never reach a decision.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from calvino.policy.config import Probability
from calvino.records import SESSION_REF_PATTERN


class ActionName(StrEnum):
    """The consequential actions of the stuck-payments workflow (TSD-002)."""

    REQUEST_CANCELLATION = "request_cancellation"
    RETRY_PAYMENT = "retry_payment"
    OPEN_INVESTIGATION = "open_investigation"


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class Scores(_Strict):
    """Calibrated probabilities from Laya. Every field is optional here; each decision requires
    the subset it reads and fails closed when one is missing."""

    needs_human: Probability | None = None
    clear_enough: Probability | None = None
    confidence: Probability | None = None
    workflow_out_of_scope: Probability | None = None
    workflow_dispute_or_fraud: Probability | None = None
    workflow_stuck_payment: Probability | None = None
    talk_to_person: Probability | None = None
    injection: Probability | None = None


ROUTE_SCORES = (
    "needs_human",
    "clear_enough",
    "confidence",
    "workflow_out_of_scope",
    "workflow_dispute_or_fraud",
    "injection",
)
GATE_SCORES = ("clear_enough", "confidence", "injection")


class Facts(_Strict):
    """What the harness knows about the session, none of it from a model.

    ``session_ref`` is already hashed (``calvino.records.session_ref_for``); the raw token never
    reaches the policy. ``amount`` and ``currency`` are given together or not at all.
    """

    session_ref: str = Field(pattern=SESSION_REF_PATTERN)
    fraud_signal: bool
    asks_for_human: bool
    auth_failures: int = Field(ge=0)
    via_regulator: bool
    vulnerable_customer: bool
    # The single entry reference the message names, if exactly one
    # (harness-detected, never a model): citing a concrete bank entry anchors
    # the turn on it. None when the message names zero or several references.
    entry_reference: str | None = Field(default=None, pattern=r"^E-[A-Z]{2}-\d{3}$")
    amount: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    currency: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _amount_and_currency_together(self) -> Facts:
        if (self.amount is None) != (self.currency is None):
            raise ValueError("amount and currency must be given together")
        return self


class GateAction(_Strict):
    """The tool call the Gate rules on."""

    name: ActionName = Field(strict=False)
    transaction_status: str = Field(min_length=1)
    amount: float = Field(ge=0, allow_inf_nan=False)
    currency: str = Field(min_length=1)
    owner_verified: bool
