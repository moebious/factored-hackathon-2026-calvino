"""Policy configuration: the pydantic model of the versioned policy files and its loader.

Every threshold and limit the policy engine reads lives in those files and nowhere else. A
released version is never edited; a change is a new file (the default loads the newest, v2), so
logged decisions replay under their version.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

# <repo>/policy/v3.yaml, found from this file (src/calvino/policy/config.py). v1 stays on disk:
# decisions logged under it replay under it (decision 30 lowered only route.min_clear_enough).
DEFAULT_POLICY_PATH = Path(__file__).resolve().parents[3] / "policy" / "v3.yaml"

Probability = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Limits = dict[str, Annotated[float, Field(gt=0, allow_inf_nan=False)]]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RoutePolicy(_Frozen):
    """Thresholds for ``decide_route``; all compare calibrated probabilities."""

    escalate_at: Probability
    act_below: Probability
    out_of_scope_at: Probability
    dispute_or_fraud_at: Probability
    injection_at: Probability
    # None switches the clear_enough gate off (policy v3): with live laya a routine, concrete
    # message scores P(clear) 0.04-0.2 because it names no payment reference, so the gate blocks
    # the requests the agent exists to answer (TSD-026).
    min_clear_enough: Probability | None
    min_confidence: Probability
    # Everything below is new in v3 and defaults to the v1/v2 behaviour, so released policy files
    # keep replaying unchanged. See TSD-026 for the measurement behind each.
    use_needs_human: bool = True  # False: the needs_human score is neither required nor read
    talk_to_person_at: Probability | None = None  # intent "talk to a person" at or above: human
    min_stuck_payment: Probability | None = None  # workflow area "stuck payment" below: clarify
    confidence_source: Literal["min_all", "workflow_area"] = "min_all"

    @model_validator(mode="after")
    def _band_is_ordered(self) -> RoutePolicy:
        # The clarify band lies between the two thresholds, so they must leave room for it.
        if not self.act_below < self.escalate_at:
            raise ValueError("act_below must be lower than escalate_at")
        return self


class HardRulesPolicy(_Frozen):
    """Parameters of the hard rules that need a number."""

    auth_failure_limit: int = Field(ge=1)
    amount_limit: Limits


class GatePolicy(_Frozen):
    """Thresholds, limits and eligibility for ``decide_gate``."""

    allow_amount_limit: Limits
    min_clear_enough: Probability
    min_confidence: Probability
    injection_at: Probability
    on_missing_scores: Literal["ask", "block"]
    eligible_statuses: dict[str, list[str]]


class Policy(_Frozen):
    """One versioned policy."""

    version: str = Field(min_length=1)
    assumptions: str = Field(min_length=1)
    route: RoutePolicy
    hard_rules: HardRulesPolicy
    gate: GatePolicy

    @model_validator(mode="after")
    def _limits_are_consistent(self) -> Policy:
        hard = self.hard_rules.amount_limit
        gate = self.gate.allow_amount_limit
        if set(hard) != set(gate):
            raise ValueError("amount limits must cover the same currencies")
        for currency, limit in gate.items():
            if limit > hard[currency]:
                raise ValueError(f"{currency}: the gate limit must not exceed the hard-rule limit")
        return self


def load_policy(path: str | Path = DEFAULT_POLICY_PATH) -> Policy:
    """Read and validate a policy file; an invalid file raises rather than loading partially."""
    with Path(path).open(encoding="utf-8") as handle:
        return Policy.model_validate(yaml.safe_load(handle))
