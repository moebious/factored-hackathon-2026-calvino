"""Dataset adapter tests (TSD-002): simulated writes, status from transaction_status only."""

from __future__ import annotations

import copy

from tests.calvino.tools.conftest import NOW, Env, build_env, load_fixture

from calvino.tools import DatasetAdapter


def test_simulated_writes_change_only_the_action_log() -> None:
    data = load_fixture()
    before = copy.deepcopy(data)
    env = build_env(DatasetAdapter(data, clock=lambda: NOW))
    s = env.session("C-MX-001")
    env.tools.request_cancellation(
        s, "E-MX-002", "k1", env.token("C-MX-001", "request_cancellation", "E-MX-002")
    )
    env.tools.retry_payment(s, "E-MX-003", "k2", env.token("C-MX-001", "retry_payment", "E-MX-003"))
    assert data == before
    assert [a["action"] for a in env.adapter.action_log] == ["cancel_payment", "retry_payment"]
    # The cancelled entry still reads as Pending: the dataset itself did not change.
    assert env.tools.get_payment_status(s, "E-MX-002").status == "Pending"


def test_an_approved_entry_with_a_null_response_code_is_approved_and_not_a_problem(
    dataset_env: Env,
) -> None:
    s = dataset_env.session("C-MX-001")
    assert dataset_env.tools.get_entry_detail(s, "E-MX-005").status == "Approved"
    assert dataset_env.tools.get_payment_status(s, "E-MX-005").status == "Approved"
    listed = {e.entry_reference for e in dataset_env.tools.list_problem_transactions(s)}
    assert "E-MX-005" not in listed
    # A null response code on a Pending or Declined entry does not change its status either.
    assert (
        dataset_env.tools.get_payment_status(dataset_env.session("C-CO-001"), "E-CO-002").status
        == "Pending"
    )
    assert (
        dataset_env.tools.get_payment_status(dataset_env.session("C-US-001"), "E-US-001").status
        == "Declined"
    )


def test_problem_transactions_are_declined_pending_and_reversed_only(dataset_env: Env) -> None:
    s = dataset_env.session("C-MX-001")
    statuses = {e.entry_reference: e.status for e in dataset_env.tools.list_problem_transactions(s)}
    assert statuses == {
        "E-MX-002": "Pending",
        "E-MX-003": "Declined",
        "E-MX-006": "Pending",
        "E-MX-007": "Reversed",
    }


def test_date_range_filters_on_booking_date(dataset_env: Env) -> None:
    from datetime import date

    s = dataset_env.session("C-MX-001")
    refs = {
        e.entry_reference
        for e in dataset_env.tools.list_problem_transactions(
            s, date(2026, 6, 10), date(2026, 6, 12)
        )
    }
    assert refs == {"E-MX-002", "E-MX-003"}


def test_an_opened_investigation_can_be_read_back_by_its_owner_only(dataset_env: Env) -> None:
    s = dataset_env.session("C-MX-001")
    case = dataset_env.tools.open_investigation(
        s,
        "E-MX-001",
        "Not mine",
        "k",
        dataset_env.token("C-MX-001", "open_investigation", "E-MX-001"),
    )
    assert dataset_env.tools.get_investigation_status(s, case.case_id) == case
