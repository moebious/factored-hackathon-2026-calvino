"""Helpers shared by ``decide_route`` and ``decide_gate``: input parsing, the hard rules and the
building of the ``DecisionRecord``.

The record keeps every input the policy read (flat, scalar, prefixed ``fact.`` or ``action.``)
plus the scores, so ``replay`` can re-run the decision from the log alone. Values that failed
validation are kept as harmless scalars (long text cut, non-finite numbers as text) so that the
replay fails closed the same way; the raw session token is never recorded.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from enum import Enum
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from calvino.policy.config import Policy
from calvino.policy.inputs import Facts, GateAction
from calvino.records import DecisionRecord, Stage, Versions

# Stored in place of a session reference that is missing or malformed (never a token).
INVALID_SESSION_REF = "0" * 64
INVALID_MARKER = "<invalid>"
_MAX_TEXT = 64

# Evaluation order of the hard rules; the first match decides.
HARD_RULE_ORDER = (
    "HR-FRAUD",
    "HR-AMOUNT",
    "HR-ASKS-HUMAN",
    "HR-AUTH",
    "HR-REGULATOR",
    "HR-VULNERABLE",
)

M = TypeVar("M", bound=BaseModel)


def as_mapping(value: object) -> dict[str, Any]:
    """A model or mapping as a plain dict; anything else is treated as empty (and so invalid)."""
    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    return {}


def parse(model: type[M], raw: Mapping[str, Any]) -> tuple[M | None, list[str]]:
    """Validate ``raw``; return the model, or None and the names of the offending fields."""
    try:
        return model.model_validate(dict(raw)), []
    except ValidationError as error:
        names = {".".join(str(part) for part in err["loc"]) or "<input>" for err in error.errors()}
        return None, sorted(names)


def triggered_hard_rules(
    facts: Facts, amount: float | None, currency: str | None, policy: Policy
) -> list[str]:
    """Ids of the hard rules that fire, in ``HARD_RULE_ORDER``. ``currency`` must be one the
    policy has limits for (callers check first)."""
    rules = policy.hard_rules
    fired = {
        "HR-FRAUD": facts.fraud_signal,
        "HR-AMOUNT": (
            amount is not None and currency is not None and amount > rules.amount_limit[currency]
        ),
        "HR-ASKS-HUMAN": facts.asks_for_human,
        "HR-AUTH": facts.auth_failures >= rules.auth_failure_limit,
        "HR-REGULATOR": facts.via_regulator,
        "HR-VULNERABLE": facts.vulnerable_customer,
    }
    return [rule for rule in HARD_RULE_ORDER if fired[rule]]


def _scalar(value: object) -> str | int | float | bool | None:
    if value is None or isinstance(value, bool | int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, Enum):
        value = value.value
    if isinstance(value, str):
        return value[:_MAX_TEXT]
    return f"<{type(value).__name__}>"


def _numbers(raw: Mapping[str, Any]) -> dict[str, float]:
    return {
        key: float(value)
        for key, value in raw.items()
        if isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)
    }


def make_record(
    *,
    kind: str,
    stage: Stage,
    policy: Policy,
    verdict: str,
    rule_id: str,
    latency_ms: float,
    raw_facts: Mapping[str, Any],
    raw_action: Mapping[str, Any] | None,
    raw_scores: Mapping[str, Any],
    threshold: float | None = None,
    input_errors: list[str] | None = None,
) -> DecisionRecord:
    """Build the record of one decision with every input that was read."""
    session_ref = raw_facts.get("session_ref")
    ref_ok = isinstance(session_ref, str) and _is_ref(session_ref)
    summary: dict[str, str | int | float | bool | None] = {"decision_kind": kind}
    for name in Facts.model_fields:
        if name == "session_ref":
            if not ref_ok:
                summary["fact.session_ref"] = INVALID_MARKER
        elif name in raw_facts:
            summary[f"fact.{name}"] = _scalar(raw_facts[name])
    if raw_action is not None:
        for name in GateAction.model_fields:
            if name in raw_action:
                summary[f"action.{name}"] = _scalar(raw_action[name])
    if threshold is not None:
        summary["threshold"] = threshold
    if input_errors:
        summary["input_error"] = ",".join(input_errors)[:200]
    return DecisionRecord(
        stage=stage,
        session_ref=session_ref if ref_ok else INVALID_SESSION_REF,  # type: ignore[arg-type]
        inputs_summary=summary,
        scores=_numbers(raw_scores),
        rule_id=rule_id,
        policy_version=policy.version,
        verdict=verdict,
        latency_ms=latency_ms,
        versions=Versions(),
    )


def _is_ref(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value)
