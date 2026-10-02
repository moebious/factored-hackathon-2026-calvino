"""Tests for the confirmation tokens (TSD-002): HMAC verifier, key handling and the fake."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from tests.calvino.tools.conftest import KEY, NOW

from calvino.tools import (
    ConfigurationError,
    FakeConfirmationVerifier,
    HmacConfirmationVerifier,
    Rule,
    ToolRefusal,
    confirmation_key_from_env,
)

ARGS = {
    "customer_id": "C-1",
    "action": "request_cancellation",
    "target_reference": "E-1",
    "amount": Decimal("10.50"),
    "currency": "MXN",
}


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


def rule_of(call) -> Rule:
    with pytest.raises(ToolRefusal) as caught:
        call()
    return caught.value.rule


def test_a_valid_token_verifies_once() -> None:
    v = HmacConfirmationVerifier(KEY, clock=lambda: NOW)
    token = v.issue(**ARGS)
    v.verify_and_consume(token, **ARGS)
    assert rule_of(lambda: v.verify_and_consume(token, **ARGS)) == Rule.TOKEN_USED


@pytest.mark.parametrize(
    "field", ["customer_id", "action", "target_reference", "amount", "currency"]
)
def test_a_token_is_bound_to_every_field(field: str) -> None:
    v = HmacConfirmationVerifier(KEY, clock=lambda: NOW)
    token = v.issue(**ARGS)
    changed = dict(ARGS)
    changed[field] = Decimal("10.51") if field == "amount" else "OTHER"
    assert rule_of(lambda: v.verify_and_consume(token, **changed)) == Rule.TOKEN_MISMATCH
    # A mismatch does not spend the token: the right request still works.
    v.verify_and_consume(token, **ARGS)


def test_an_equal_amount_written_differently_matches() -> None:
    v = HmacConfirmationVerifier(KEY, clock=lambda: NOW)
    token = v.issue(**{**ARGS, "amount": Decimal("10.5")})
    v.verify_and_consume(token, **ARGS)


def test_a_token_expires() -> None:
    clock = Clock()
    v = HmacConfirmationVerifier(KEY, ttl=timedelta(minutes=5), clock=clock)
    token = v.issue(**ARGS)
    clock.now = NOW + timedelta(minutes=5)
    assert rule_of(lambda: v.verify_and_consume(token, **ARGS)) == Rule.TOKEN_EXPIRED


def test_tampered_missing_and_foreign_tokens_are_refused() -> None:
    v = HmacConfirmationVerifier(KEY, clock=lambda: NOW)
    token = v.issue(**ARGS)
    body, _, sig = token.partition(".")
    other = HmacConfirmationVerifier(b"another-key-0123456789-abcdefghijk", clock=lambda: NOW)
    flipped = sig[:-1] + ("1" if sig[-1] == "0" else "0")  # always differs from the real signature
    for bad in (f"{body}x.{sig}", f"{body}.{flipped}", "garbage", "", other.issue(**ARGS)):
        assert rule_of(lambda bad=bad: v.verify_and_consume(bad, **ARGS)) in (
            Rule.TOKEN_INVALID,
            Rule.TOKEN_MISSING,
        )
    assert rule_of(lambda: v.verify_and_consume(None, **ARGS)) == Rule.TOKEN_MISSING


def test_the_server_refuses_to_start_without_a_key() -> None:
    for env in ({}, {"CALVINO_CONFIRMATION_KEY": ""}, {"CALVINO_CONFIRMATION_KEY": "short"}):
        with pytest.raises(ConfigurationError) as caught:
            confirmation_key_from_env(env)
        assert caught.value.rule == Rule.CONFIG
    with pytest.raises(ConfigurationError):
        HmacConfirmationVerifier(b"short")
    assert confirmation_key_from_env({"CALVINO_CONFIRMATION_KEY": "x" * 32}) == b"x" * 32


def test_the_fake_accepts_only_granted_actions_once() -> None:
    fake = FakeConfirmationVerifier()
    token = fake.grant(**ARGS)
    assert (
        rule_of(lambda: fake.verify_and_consume(token, **{**ARGS, "target_reference": "E-2"}))
        == Rule.TOKEN_INVALID
    )
    fake.verify_and_consume(token, **ARGS)
    assert rule_of(lambda: fake.verify_and_consume(token, **ARGS)) == Rule.TOKEN_INVALID
    assert rule_of(lambda: fake.verify_and_consume(None, **ARGS)) == Rule.TOKEN_MISSING


def test_now_is_utc_aware() -> None:
    assert NOW.tzinfo is UTC
