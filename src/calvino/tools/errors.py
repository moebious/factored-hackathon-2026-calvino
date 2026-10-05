"""Stable rule ids for every refusal a tool can make (TSD-002).

A refusal always names the rule that fired, so the hub can log it, the oracle can score it and a
test can assert it. The ids are part of the tool contract: add new ones, never rename.

The hub must not relay ``TOOL-FRAUD-FLAGGED`` to the customer: telling someone that a fraud flag
is the reason tips them off. It routes the case to a person instead.
"""

from __future__ import annotations

from enum import StrEnum


class Rule(StrEnum):
    """The rule behind a refusal."""

    NO_SESSION = "TOOL-NO-SESSION"
    SESSION_EXPIRED = "TOOL-SESSION-EXPIRED"
    NOT_OWNER = "TOOL-NOT-OWNER"
    NOT_FOUND = "TOOL-NOT-FOUND"
    INELIGIBLE = "TOOL-INELIGIBLE"
    FRAUD_FLAGGED = "TOOL-FRAUD-FLAGGED"
    TOKEN_MISSING = "TOOL-TOKEN-MISSING"
    TOKEN_INVALID = "TOOL-TOKEN-INVALID"
    TOKEN_EXPIRED = "TOOL-TOKEN-EXPIRED"
    TOKEN_MISMATCH = "TOOL-TOKEN-MISMATCH"
    TOKEN_USED = "TOOL-TOKEN-USED"
    IDEMPOTENCY_CONFLICT = "TOOL-IDEMPOTENCY-CONFLICT"
    BAD_INPUT = "TOOL-BAD-INPUT"
    SOURCE_INCOMPLETE = "TOOL-SOURCE-INCOMPLETE"
    CONFIG = "TOOL-CONFIG"


class ToolRefusal(Exception):
    """A tool refused to act; ``rule`` says why. The message holds no other customer's data."""

    def __init__(self, rule: Rule, message: str) -> None:
        super().__init__(f"{rule.value}: {message}")
        self.rule = rule
        self.message = message


class ConfigurationError(ToolRefusal):
    """The server is misconfigured (for example no confirmation key); it must not start."""

    def __init__(self, message: str) -> None:
        super().__init__(Rule.CONFIG, message)
