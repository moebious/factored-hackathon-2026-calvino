"""Shared types every Calvino stream builds on (TSD-000).

The enums name the verdicts the hub can reach; ``DecisionRecord`` is one line of the audit log
(``decisions.jsonl``), written for every decision with its inputs, scores, rule and versions so
that any verdict can be explained and replayed.
"""

from __future__ import annotations

import hashlib
import math
import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

# A session reference is the hex SHA-256 digest of the session token: 64 lowercase hex characters.
# Anything else (a raw token, a JWT, a shorter hash) is rejected, so a token can never reach the
# log by accident. A raw token that is itself 64 hex characters would pass this check; the hub
# avoids that by always building the reference with ``session_ref_for``.
SESSION_REF_PATTERN = r"^[0-9a-f]{64}$"


class Route(StrEnum):
    """Where the hub sends a request after the hard rules and the classifiers."""

    AGENTS = "agents"
    # Not in the first draft of TSD-000: the policy's uncertain band (TSD-001) and the workflow's
    # clarify stage (decision 17) need a route of their own.
    CLARIFY = "clarify"
    HUMAN = "human"
    OUT_OF_SCOPE = "out_of_scope"


class GateVerdict(StrEnum):
    """The Gate's answer before a tool call: run it, ask a person, or refuse."""

    ALLOW = "allow"
    ASK = "ask"
    BLOCK = "block"


class HumanAction(StrEnum):
    """How a person is involved, as decided by the human intervention classifier."""

    NONE = "none"
    APPROVE_ACTION = "approve_action"
    REQUEST_INFO = "request_info"
    FULL_TRANSFER = "full_transfer"


class Stage(StrEnum):
    """The part of the hub that made a decision."""

    HARD_RULES = "hard_rules"
    CLASSIFIER = "classifier"
    GATE = "gate"
    VERIFIER = "verifier"
    HUMAN = "human"


class Versions(BaseModel):
    """Versions of everything that can change a verdict; missing parts are left empty."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model: str | None = None
    checkpoint: str | None = None
    prompt: str | None = None
    rubric: str | None = None


def session_ref_for(token: str) -> str:
    """Return the reference stored in the log for a session token: its SHA-256 hex digest."""
    if not token:
        raise ValueError("session token must not be empty")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(UTC)


class DecisionRecord(BaseModel):
    """One decision, as written to the audit log.

    ``inputs_summary`` must already be redacted by the caller: this model checks types, not
    content. ``verdict`` holds the enum value of whatever was decided (a ``Route``, a
    ``GateVerdict``, a ``HumanAction``) or a verifier's pass or fail, so it is kept as text.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=_utc_now)
    stage: Stage
    session_ref: str = Field(pattern=SESSION_REF_PATTERN)
    inputs_summary: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    scores: dict[str, float] = Field(default_factory=dict)
    rule_id: str | None = None
    policy_version: str = Field(min_length=1)
    verdict: str = Field(min_length=1)
    latency_ms: float = Field(ge=0)
    cost_usd: float = Field(default=0.0, ge=0)
    versions: Versions = Field(default_factory=Versions)

    @field_validator("timestamp")
    @classmethod
    def _timestamp_is_aware(cls, value: datetime) -> datetime:
        # Naive timestamps make replays across machines ambiguous, so they are refused.
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value

    @field_validator("scores")
    @classmethod
    def _scores_are_finite(cls, value: dict[str, float]) -> dict[str, float]:
        for name, score in value.items():
            if not math.isfinite(score):
                raise ValueError(f"score {name!r} is not a finite number")
        return value
