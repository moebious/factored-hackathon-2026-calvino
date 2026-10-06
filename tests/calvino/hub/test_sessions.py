"""Tests for calvino.hub.sessions: trusted test sessions issued by the hub."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from calvino.hub.sessions import DEFAULT_SESSION_TTL, TrustedSessionIssuer
from calvino.records import session_ref_for

PERSONAS = {"maria": "C-MX-001", "juan": "C-CO-001"}
NOW = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)


def make_issuer(**kwargs) -> TrustedSessionIssuer:
    counter = iter(range(1000))
    return TrustedSessionIssuer(PERSONAS, token_factory=lambda: f"tok-{next(counter)}", **kwargs)


def test_issue_returns_token_and_session_ref() -> None:
    issuer = make_issuer()
    token, session_ref = issuer.issue("maria", now=NOW)
    assert token == "tok-0"
    assert session_ref == session_ref_for(token)


def test_issued_session_resolves_for_the_right_customer() -> None:
    issuer = make_issuer()
    token, _ = issuer.issue("juan", now=NOW)
    session = issuer.resolve(token, now=NOW)
    assert session is not None
    assert session.customer_id == "C-CO-001"
    assert session.expires_at == NOW + DEFAULT_SESSION_TTL


def test_unknown_persona_raises() -> None:
    # A persona nobody signed in as never gets a session, not even a fallback.
    issuer = make_issuer()
    with pytest.raises(KeyError, match="nobody"):
        issuer.issue("nobody", now=NOW)


def test_unknown_and_non_string_tokens_resolve_to_none() -> None:
    issuer = make_issuer()
    assert issuer.resolve("tok-unknown", now=NOW) is None
    assert issuer.resolve(None, now=NOW) is None
    assert issuer.resolve(42, now=NOW) is None


def test_expired_token_resolves_to_none() -> None:
    # Fail closed: the tools' require_session refuses, and the resolver agrees.
    issuer = make_issuer()
    token, _ = issuer.issue("maria", now=NOW)
    later = NOW + DEFAULT_SESSION_TTL
    assert issuer.resolve(token, now=later) is None
    assert issuer.resolve(token, now=later - timedelta(seconds=1)) is not None


def test_tokens_are_unique_per_issue() -> None:
    issuer = make_issuer()
    first, _ = issuer.issue("maria", now=NOW)
    second, _ = issuer.issue("maria", now=NOW)
    assert first != second
    assert issuer.resolve(first, now=NOW).customer_id == "C-MX-001"
    assert issuer.resolve(second, now=NOW).customer_id == "C-MX-001"


def test_empty_personas_are_rejected() -> None:
    with pytest.raises(ValueError, match="at least one persona"):
        TrustedSessionIssuer({})


def test_personas_lists_the_demo_sign_ins() -> None:
    assert make_issuer().personas() == ("maria", "juan")


def test_issue_customer_for_sandbox_guest() -> None:
    issuer = make_issuer()
    token, session_ref = issuer.issue_customer(now=NOW)
    assert token == "tok-0"
    assert session_ref == session_ref_for(token)
    session = issuer.resolve(token, now=NOW)
    assert session is not None
    assert session.customer_id == "C-MX-001"
