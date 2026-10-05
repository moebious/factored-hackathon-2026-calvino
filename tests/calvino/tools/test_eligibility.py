"""Eligibility tests (TSD-002): cancel only Pending, retry only Declined, never fraud-flagged.

Eligibility lives in the tool; amount limits and asking a person belong to the Gate (TSD-001).
Each refusal names its rule, and a refused call never touches the action log.
"""

from __future__ import annotations

import pytest
from tests.calvino.tools.conftest import Env

from calvino.tools import Rule, ToolRefusal


def cancel(env: Env, customer: str, ref: str):
    return env.tools.request_cancellation(
        env.session(customer), ref, f"k-{ref}", env.token(customer, "request_cancellation", ref)
    )


def retry(env: Env, customer: str, ref: str):
    return env.tools.retry_payment(
        env.session(customer), ref, f"k-{ref}", env.token(customer, "retry_payment", ref)
    )


def refused(call) -> ToolRefusal:
    with pytest.raises(ToolRefusal) as caught:
        call()
    return caught.value


def test_a_pending_transfer_can_be_cancelled(dataset_env: Env) -> None:
    result = cancel(dataset_env, "C-MX-001", "E-MX-002")
    assert result.outcome == "accepted" and result.simulated
    assert dataset_env.adapter.action_log[0]["action"] == "cancel_payment"


def test_a_declined_transfer_can_be_retried_as_a_new_payment(dataset_env: Env) -> None:
    result = retry(dataset_env, "C-MX-001", "E-MX-003")
    assert result.simulated and result.original_reference == "E-MX-003"
    assert result.new_payment.original_reference.startswith("RTY-")
    assert result.new_payment.status == "Pending"


@pytest.mark.parametrize("ref", ["E-MX-004", "E-MX-003", "E-MX-007"])
def test_cancelling_a_non_pending_transfer_is_refused(dataset_env: Env, ref: str) -> None:
    err = refused(lambda: cancel(dataset_env, "C-MX-001", ref))
    assert err.rule == Rule.INELIGIBLE and "Pending" in err.message
    assert dataset_env.adapter.action_log == []


@pytest.mark.parametrize("ref", ["E-MX-002", "E-MX-004", "E-MX-007"])
def test_retrying_a_non_declined_transfer_is_refused(dataset_env: Env, ref: str) -> None:
    err = refused(lambda: retry(dataset_env, "C-MX-001", ref))
    assert err.rule == Rule.INELIGIBLE and "Declined" in err.message
    assert dataset_env.adapter.action_log == []


def test_a_pending_card_purchase_cannot_be_cancelled(dataset_env: Env) -> None:
    assert refused(lambda: cancel(dataset_env, "C-MX-001", "E-MX-006")).rule == Rule.INELIGIBLE


@pytest.mark.parametrize(
    ("fn", "ref"),
    [(cancel, "E-AR-001"), (retry, "E-AR-002"), (cancel, "E-AR-002"), (retry, "E-AR-001")],
)
def test_fraud_flagged_transactions_are_never_acted_on(dataset_env: Env, fn, ref: str) -> None:
    assert refused(lambda: fn(dataset_env, "C-AR-001", ref)).rule == Rule.FRAUD_FLAGGED
    assert dataset_env.adapter.action_log == []


def test_the_fraud_flag_is_not_visible_in_any_output(dataset_env: Env) -> None:
    s = dataset_env.session("C-AR-001")
    for entry in dataset_env.tools.list_problem_transactions(s):
        assert "fraud" not in entry.model_dump_json().lower()
    assert (
        "fraud" not in dataset_env.tools.get_payment_status(s, "E-AR-002").model_dump_json().lower()
    )


def test_an_investigation_can_be_opened_even_on_a_fraud_flagged_entry(dataset_env: Env) -> None:
    case = dataset_env.tools.open_investigation(
        dataset_env.session("C-AR-001"),
        "E-AR-001",
        "I did not make this transfer",
        "k",
        dataset_env.token("C-AR-001", "open_investigation", "E-AR-001"),
    )
    assert case.status == "Open" and case.related_entry_reference == "E-AR-001"


@pytest.mark.parametrize(
    ("tool", "entry_reference"),
    [
        ("request_cancellation", "E-MX-002"),
        ("retry_payment", "E-MX-003"),
        ("open_investigation", "E-MX-001"),
    ],
)
@pytest.mark.parametrize("missing_field", ["amount", "currency"])
def test_missing_confirmation_facts_refuse_before_consuming_token_or_writing(
    dataset_env: Env, tool: str, entry_reference: str, missing_field: str
) -> None:
    session = dataset_env.session("C-MX-001")
    original = dataset_env.adapter._records[entry_reference]
    token = dataset_env.token("C-MX-001", tool, entry_reference)
    dataset_env.adapter._records[entry_reference] = original.model_copy(
        update={
            "entry": original.entry.model_copy(update={missing_field: None}),
        }
    )

    with pytest.raises(ToolRefusal) as caught:
        if tool == "request_cancellation":
            dataset_env.tools.request_cancellation(session, entry_reference, "missing-fact", token)
        elif tool == "retry_payment":
            dataset_env.tools.retry_payment(session, entry_reference, "missing-fact", token)
        else:
            dataset_env.tools.open_investigation(
                session, entry_reference, "Customer asks for help", "missing-fact", token
            )

    assert caught.value.rule is Rule.SOURCE_INCOMPLETE
    assert dataset_env.adapter.action_log == []
    dataset_env.verifier.verify_and_consume(
        token,
        customer_id="C-MX-001",
        action=tool,
        target_reference=entry_reference,
        amount=original.entry.amount,
        currency=original.entry.currency,
    )


@pytest.mark.parametrize(
    ("tool", "entry_reference"),
    [
        ("request_cancellation", "E-MX-002"),
        ("retry_payment", "E-MX-003"),
    ],
)
def test_unknown_fraud_status_refuses_before_consuming_token(
    dataset_env: Env, tool: str, entry_reference: str
) -> None:
    session = dataset_env.session("C-MX-001")
    original = dataset_env.adapter._records[entry_reference]
    token = dataset_env.token("C-MX-001", tool, entry_reference)
    dataset_env.adapter._records[entry_reference] = original.model_copy(
        update={"fraud_flagged": None}
    )

    with pytest.raises(ToolRefusal) as caught:
        if tool == "request_cancellation":
            dataset_env.tools.request_cancellation(session, entry_reference, "unknown-fraud", token)
        else:
            dataset_env.tools.retry_payment(session, entry_reference, "unknown-fraud", token)

    assert caught.value.rule is Rule.SOURCE_INCOMPLETE
    assert dataset_env.adapter.action_log == []
    dataset_env.verifier.verify_and_consume(
        token,
        customer_id="C-MX-001",
        action=tool,
        target_reference=entry_reference,
        amount=original.entry.amount,
        currency=original.entry.currency,
    )
