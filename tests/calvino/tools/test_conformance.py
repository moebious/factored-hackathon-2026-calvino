"""Adapter conformance suite (TSD-002): what every bank adapter must pass.

Parametrized over ``ADAPTER_FACTORIES`` in conftest.py through the ``env`` fixture, so a future
adapter only has to be added there. Covers schema validity, ownership checks, error codes and
idempotency, all through ``BankTools`` so the adapter is tested as the hub will use it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from tests.calvino.tools.conftest import Env

from calvino.tools import Rule, ToolRefusal
from calvino.tools.contracts import SCHEMA_MODELS

CONTRACTS = Path(__file__).resolve().parents[3] / "contracts" / "tools"


def assert_valid(name: str, value) -> None:
    schema = json.loads((CONTRACTS / f"{name}.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(json.loads(value.model_dump_json()))


def refusal(call) -> Rule:
    with pytest.raises(ToolRefusal) as caught:
        call()
    return caught.value.rule


def test_every_contract_has_a_schema_file() -> None:
    for name in SCHEMA_MODELS:
        assert (CONTRACTS / f"{name}.schema.json").exists()


def test_reads_return_valid_contracts(env: Env) -> None:
    s = env.session("C-MX-001")
    assert_valid("customer-summary", env.tools.get_customer_summary(s))
    for account in env.tools.list_accounts(s):
        assert_valid("account", account)
    account_id = env.tools.list_accounts(s)[0].account_id
    entries = env.tools.get_account_entries(s, account_id)
    assert entries
    for entry in entries:
        assert_valid("account-entry", entry)
    assert_valid("account-entry", env.tools.get_entry_detail(s, "E-MX-001"))
    assert_valid("payment-status", env.tools.get_payment_status(s, "E-MX-003"))
    assert env.tools.list_problem_transactions(s)


def test_writes_return_valid_contracts(env: Env) -> None:
    s = env.session("C-MX-001")
    cancel = env.tools.request_cancellation(
        s, "E-MX-002", "k1", env.token("C-MX-001", "request_cancellation", "E-MX-002")
    )
    assert_valid("cancellation-response", cancel)
    retry = env.tools.retry_payment(
        s, "E-MX-003", "k2", env.token("C-MX-001", "retry_payment", "E-MX-003")
    )
    assert_valid("retry-result", retry)
    case = env.tools.open_investigation(
        s, "E-MX-001", "Not mine", "k3", env.token("C-MX-001", "open_investigation", "E-MX-001")
    )
    assert_valid("investigation", case)
    assert_valid("investigation", env.tools.get_investigation_status(s, case.case_id))
    assert cancel.simulated and retry.simulated and "SIMULATED" in cancel.message


@pytest.mark.parametrize(
    "call",
    [
        lambda t, s: t.get_entry_detail(s, "E-CO-001"),
        lambda t, s: t.get_payment_status(s, "E-CO-001"),
    ],
)
def test_other_customers_records_are_refused_as_not_owner(env: Env, call) -> None:
    assert refusal(lambda: call(env.tools, env.session("C-MX-001"))) == Rule.NOT_OWNER


def test_other_customers_products_are_refused_as_not_owner(env: Env) -> None:
    other_account = env.tools.list_accounts(env.session("C-CO-001"))[0]
    assert (
        refusal(
            lambda: env.tools.get_account_entries(env.session("C-MX-001"), other_account.account_id)
        )
        == Rule.NOT_OWNER
    )


def test_other_customers_cases_are_refused_as_not_owner(env: Env) -> None:
    owner_session = env.session("C-CO-001")
    case = env.tools.open_investigation(
        owner_session,
        "E-CO-001",
        "Synthetic test case",
        "case-owner-check",
        env.token("C-CO-001", "open_investigation", "E-CO-001"),
    )

    assert (
        refusal(lambda: env.tools.get_investigation_status(env.session("C-MX-001"), case.case_id))
        == Rule.NOT_OWNER
    )


@pytest.mark.parametrize(
    "call",
    [
        lambda t, s: t.get_entry_detail(s, "E-NOPE"),
        lambda t, s: t.get_payment_status(s, "E-NOPE"),
        lambda t, s: t.get_account_entries(s, "A-NOPE"),
        lambda t, s: t.get_investigation_status(s, "CASE-NOPE"),
    ],
)
def test_missing_records_are_refused_as_not_found(env: Env, call) -> None:
    assert refusal(lambda: call(env.tools, env.session("C-MX-001"))) == Rule.NOT_FOUND


def test_lists_only_contain_the_sessions_customer(env: Env) -> None:
    for customer, prefix in (("C-MX-001", "E-MX"), ("C-CO-001", "E-CO"), ("C-AR-001", "E-AR")):
        entries = env.tools.list_problem_transactions(env.session(customer))
        assert entries and all(e.entry_reference.startswith(prefix) for e in entries)
        for account in env.tools.list_accounts(env.session(customer)):
            env.tools.get_account_entries(env.session(customer), account.account_id)


def test_a_repeated_write_replays_the_first_result(env: Env) -> None:
    s = env.session("C-MX-001")
    first = env.tools.request_cancellation(
        s, "E-MX-002", "same-key", env.token("C-MX-001", "request_cancellation", "E-MX-002")
    )
    # The token was consumed: a replay needs no new token and returns the same result.
    again = env.tools.request_cancellation(s, "E-MX-002", "same-key", "not-a-token")
    assert again == first


def test_the_same_key_for_another_target_is_a_conflict(env: Env) -> None:
    s = env.session("C-MX-001")
    env.tools.request_cancellation(
        s, "E-MX-002", "k", env.token("C-MX-001", "request_cancellation", "E-MX-002")
    )
    rule = refusal(lambda: env.tools.request_cancellation(s, "E-MX-006", "k", "whatever"))
    assert rule == Rule.IDEMPOTENCY_CONFLICT


def test_bad_inputs_are_refused(env: Env) -> None:
    s = env.session("C-MX-001")
    assert refusal(lambda: env.tools.request_cancellation(s, "E-MX-002", "", "t")) == Rule.BAD_INPUT
    assert (
        refusal(
            lambda: env.tools.list_problem_transactions(
                s, date_from=_d(2026, 7, 1), date_to=_d(2026, 6, 1)
            )
        )
        == Rule.BAD_INPUT
    )


def _d(y: int, m: int, d: int):
    from datetime import date

    return date(y, m, d)
