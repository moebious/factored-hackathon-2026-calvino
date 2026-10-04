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


def test_the_question_is_kept_as_a_digest_and_never_as_the_raw_message():
    """question-fully-answered needs the question; NFR-1 says it cannot leave as written.

    The judge is an external model producing blocking verdicts, so it gets the redacted digest.
    """
    results = [
        ToolResult(
            tool="payment_status",
            payload={"status": "PENDING", "amount": "49.90", "remittance_information": "ACME LTD"},
        )
    ]
    evidence = evidence_from_tool_results(
        results,
        message="Llevo 5 dias pagando a ACME LTD y ya me han cobrado 49.90 dos veces",
    )
    assert evidence.customer_question is not None
    assert "ACME LTD" not in evidence.customer_question, (
        "the merchant travels as evidence, not as prose"
    )
    assert "49.90" not in evidence.customer_question, "the amount travels as evidence, not as prose"
    assert "<merchant>" in evidence.customer_question
    assert "<amount>" in evidence.customer_question
    # The substance survives, which is the whole point: was the reply asked anything?
    assert "dos veces" in evidence.customer_question


def test_another_customers_markers_are_redacted_from_the_question():
    evidence = evidence_from_tool_results(
        [],
        message="Mi maxima es de 900 y el titular es Marta Ruiz",
        forbidden_markers=["Marta Ruiz"],
    )
    assert evidence.customer_question is not None
    assert "Marta Ruiz" not in evidence.customer_question
    assert "<redacted>" in evidence.customer_question


def test_no_question_stays_distinguishable_from_a_redacted_one():
    """The prompt renders "not provided", so an empty turn must not look like a redaction."""
    assert evidence_from_tool_results([]).customer_question is None
    assert evidence_from_tool_results([], message="   ").customer_question is None


def test_a_long_question_is_capped():
    evidence = evidence_from_tool_results([], message="palabra " * 200)
    assert evidence.customer_question is not None
    assert len(evidence.customer_question) <= 240
    assert evidence.customer_question.endswith("…"), (
        "a truncated question says so rather than pretending"
    )


def test_whitespace_is_collapsed_so_length_is_not_a_disclosure():
    evidence = evidence_from_tool_results([], message="hola\n\n\t  otra   vez   ")
    assert evidence.customer_question == "hola otra vez"


def test_amounts_are_matched_by_value_not_by_spelling():
    """The contracts say "5000.00" and the customer types "5000"; both are the same disclosure."""
    results = [ToolResult(tool="payment_status", payload={"amount": "5000.00"})]
    for typed in ("5000", "5000.00", "5,000.00", "$5000"):
        evidence = evidence_from_tool_results(results, message=f"mi pago de {typed} pesos")
        assert evidence.customer_question is not None, typed
        assert "5000" not in evidence.customer_question.replace("<amount>", ""), typed


def test_a_number_that_is_not_an_evidence_amount_survives():
    """Redacting every digit would make the digest unreadable and hide nothing."""
    evidence = evidence_from_tool_results(
        [ToolResult(tool="payment_status", payload={"amount": "5000.00"})],
        message="llevo 5 dias esperando y me cobraron 2 veces",
    )
    assert evidence.customer_question is not None
    assert "5 dias" in evidence.customer_question
    assert "2 veces" in evidence.customer_question


def test_an_unparseable_number_is_left_alone():
    """A reference like E-MX-002.5 must not crash the turn or silently vanish."""
    evidence = evidence_from_tool_results(
        [ToolResult(tool="payment_status", payload={"amount": "10"})],
        message="referencia 1.234.5 y referencia E-MX-002",
    )
    assert evidence.customer_question is not None
    assert "E-MX-002" in evidence.customer_question
