"""Security tests (TSD-002): another customer, no or expired session, invalid tokens."""

from __future__ import annotations

from datetime import timedelta

import pytest
from tests.calvino.tools.conftest import Env

from calvino.tools import Rule, ToolRefusal


def rule_of(call) -> Rule:
    with pytest.raises(ToolRefusal) as caught:
        call()
    return caught.value.rule


def test_no_session_is_refused_for_every_tool(env: Env) -> None:
    t = env.tools
    calls = [
        lambda: t.get_customer_summary(None),
        lambda: t.list_accounts(None),
        lambda: t.get_account_entries(None, "A-MX-001"),
        lambda: t.get_entry_detail(None, "E-MX-001"),
        lambda: t.get_payment_status(None, "E-MX-001"),
        lambda: t.list_problem_transactions(None),
        lambda: t.get_investigation_status(None, "CASE-0001"),
        lambda: t.request_cancellation(None, "E-MX-002", "k", "t"),
        lambda: t.retry_payment(None, "E-MX-003", "k", "t"),
        lambda: t.open_investigation(None, "E-MX-001", "r", "k", "t"),
    ]
    assert {rule_of(c) for c in calls} == {Rule.NO_SESSION}


def test_an_expired_session_is_refused(env: Env) -> None:
    expired = env.session("C-MX-001", ttl=timedelta(seconds=-1))
    assert rule_of(lambda: env.tools.list_accounts(expired)) == Rule.SESSION_EXPIRED
    token = env.token("C-MX-001", "request_cancellation", "E-MX-002")
    assert (
        rule_of(lambda: env.tools.request_cancellation(expired, "E-MX-002", "k", token))
        == Rule.SESSION_EXPIRED
    )


def test_customer_a_cannot_write_on_customer_bs_record(env: Env) -> None:
    # Even with a token that is valid for B's record, A's session cannot use it.
    token_for_b = env.token("C-CO-001", "request_cancellation", "E-CO-003")
    a = env.session("C-MX-001")
    rule = rule_of(lambda: env.tools.request_cancellation(a, "E-CO-003", "k", token_for_b))
    assert rule == Rule.NOT_OWNER
    assert env.adapter.action_log == []


@pytest.mark.parametrize("token", [None, "", "garbage", "a.b"])
def test_a_write_without_a_valid_token_is_refused_and_does_nothing(env: Env, token) -> None:
    s = env.session("C-MX-001")
    rule = rule_of(lambda: env.tools.request_cancellation(s, "E-MX-002", "k", token))
    assert rule in (Rule.TOKEN_MISSING, Rule.TOKEN_INVALID)
    assert env.adapter.action_log == []


def test_idempotency_keys_do_not_leak_across_customers(env: Env) -> None:
    # Customer A acts under a key; customer B reuses the same key.
    a = env.session("C-MX-001")
    first = env.tools.request_cancellation(
        a,
        "E-MX-002",
        "shared-key",
        env.token("C-MX-001", "request_cancellation", "E-MX-002"),
    )
    b = env.session("C-CO-001")
    # B gets B's own result, never A's, and still needs B's own token.
    assert (
        rule_of(lambda: env.tools.request_cancellation(b, "E-CO-003", "shared-key", None))
        == Rule.TOKEN_MISSING
    )
    second = env.tools.request_cancellation(
        b,
        "E-CO-003",
        "shared-key",
        env.token("C-CO-001", "request_cancellation", "E-CO-003"),
    )
    assert first.original_reference == "E-MX-002"
    assert second.original_reference == "E-CO-003"
    assert second.requested_by == "C-CO-001"
    # B asking for A's entry under A's key is refused as not-owner, with no replay of A's result.
    assert (
        rule_of(lambda: env.tools.request_cancellation(b, "E-MX-002", "shared-key", None))
        == Rule.NOT_OWNER
    )


def test_a_token_works_once(env: Env) -> None:
    s = env.session("C-MX-001")
    token = env.token("C-MX-001", "request_cancellation", "E-MX-002")
    env.tools.request_cancellation(s, "E-MX-002", "k1", token)
    # A new key with the same token is a new request, and the token is spent.
    assert (
        rule_of(lambda: env.tools.request_cancellation(s, "E-MX-002", "k2", token))
        == Rule.TOKEN_USED
    )


def test_a_token_for_one_action_does_not_authorize_another(env: Env) -> None:
    s = env.session("C-MX-001")
    cancel_token = env.token("C-MX-001", "request_cancellation", "E-MX-002")
    rule = rule_of(lambda: env.tools.open_investigation(s, "E-MX-002", "r", "k", cancel_token))
    assert rule == Rule.TOKEN_MISMATCH
    other_target = env.token("C-MX-001", "request_cancellation", "E-MX-006")
    assert (
        rule_of(lambda: env.tools.request_cancellation(s, "E-MX-002", "k2", other_target))
        == Rule.TOKEN_MISMATCH
    )
