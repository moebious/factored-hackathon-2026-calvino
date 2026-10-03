"""Tests for the evidence collection (TSD-004): what the code checks may compare against."""

from datetime import date
from decimal import Decimal

from calvino.tools.contracts import TransactionStatus
from calvino.verifier.evidence import ToolResult, evidence_from_tool_results

ENTRY_PAYLOAD = {
    "entry_reference": "ENT-1",
    "amount": "1500.00",
    "currency": "MXN",
    "credit_debit": "DBIT",
    "status": "Pending",
    "booking_date": "2026-09-28",
    "value_date": "2026-09-29",
    "bank_transaction_code": "PMNT-RCDT-ESCT",
    "remittance_information": "Aeromexico vacaciones",
    "merchant_category_code": "4722",
    "country": "MX",
}


def test_collects_amounts_dates_merchants_and_statuses():
    evidence = evidence_from_tool_results(
        [
            ToolResult(tool="list_account_entries", payload={"entries": [ENTRY_PAYLOAD]}),
            ToolResult(
                tool="get_payment_status",
                payload={"original_reference": "PAY-1", "status": "Declined", "reason": "funds"},
            ),
        ]
    )
    assert evidence.amounts == frozenset({Decimal("1500.00")})
    assert evidence.dates == frozenset({date(2026, 9, 28), date(2026, 9, 29)})
    assert evidence.merchants == frozenset({"Aeromexico vacaciones"})
    assert evidence.statuses == frozenset({TransactionStatus.PENDING, TransactionStatus.DECLINED})


def test_datetime_fields_contribute_their_date_part():
    evidence = evidence_from_tool_results(
        [
            ToolResult(
                tool="open_investigation",
                payload={
                    "case_id": "CASE-1",
                    "related_entry_reference": "ENT-1",
                    "reason": "stuck",
                    "status": "Open",  # an investigation status, not a transaction status
                    "opened_at": "2026-09-30T10:15:00+00:00",
                },
            )
        ]
    )
    assert evidence.dates == frozenset({date(2026, 9, 30)})
    assert evidence.statuses == frozenset()


def test_non_transaction_statuses_and_bad_amounts_are_skipped():
    evidence = evidence_from_tool_results(
        [
            ToolResult(
                tool="get_account",
                payload={"account_id": "ACC-1", "status": "active", "balance": "not-a-number"},
            )
        ]
    )
    assert evidence.statuses == frozenset()
    assert evidence.amounts == frozenset()


def test_caller_supplied_facts_are_carried_through():
    evidence = evidence_from_tool_results(
        [],
        customer_language="pt",
        read_backs={"cancel_transfer"},
        forbidden_markers={"CUST-777"},
    )
    assert evidence.customer_language == "pt"
    assert evidence.read_backs == frozenset({"cancel_transfer"})
    assert evidence.forbidden_markers == frozenset({"CUST-777"})


def test_defaults_to_empty_spanish_evidence():
    evidence = evidence_from_tool_results([])
    assert evidence.customer_language == "es"
    assert evidence.amounts == frozenset()
    assert evidence.read_backs == frozenset()
