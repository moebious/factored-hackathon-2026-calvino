"""Tests for the code check registry (TSD-004): every check, passing and failing."""

from datetime import date
from decimal import Decimal

import pytest

from calvino.tools.contracts import TransactionStatus
from calvino.verifier.code_checks import (
    CODE_CHECKS,
    check_amounts_dates_merchants,
    check_claimed_actions_read_back,
    check_no_money_movement_promise,
    check_no_other_customer_data,
    check_reply_language,
    check_stated_status,
    run_code_checks,
)
from calvino.verifier.evidence import Evidence
from calvino.verifier.rubric import CheckerKind, Rubric, load_rubric

EVIDENCE = Evidence(
    amounts=frozenset({Decimal("1500.00")}),
    dates=frozenset({date(2026, 9, 28), date(2026, 9, 29)}),
    merchants=frozenset({"Aeromexico vacaciones"}),
    statuses=frozenset({TransactionStatus.PENDING}),
    customer_language="es",
    read_backs=frozenset({"cancel_transfer"}),
    forbidden_markers=frozenset({"CUST-777", "Ana Lopez"}),
)


def test_amounts_dates_merchants_pass():
    text = "Su transferencia de 1,500.00 MXN del 2026-09-28 a «Aeromexico vacaciones»."
    verdict = check_amounts_dates_merchants(text, EVIDENCE)
    assert verdict.passed
    assert verdict.checker is CheckerKind.CODE


def test_amounts_pass_in_spanish_format():
    verdict = check_amounts_dates_merchants("El monto es 1.500,00 MXN.", EVIDENCE)
    assert verdict.passed


def test_plain_contract_amounts_pass():
    # Contracts serialize amounts without thousand separators ("5000.00");
    # quoting one verbatim must match the evidence instead of splitting into
    # a stray decimal token that no tool result carries.
    plain = EVIDENCE.model_copy(update={"amounts": frozenset({Decimal("5000.00")})})
    assert check_amounts_dates_merchants("Su transferencia de 5000.00 MXN.", plain).passed
    long_plain = EVIDENCE.model_copy(update={"amounts": frozenset({Decimal("50000.00")})})
    assert check_amounts_dates_merchants("El saldo es de 50000.00 MXN.", long_plain).passed


def test_unknown_amount_fails():
    verdict = check_amounts_dates_merchants("Le devolvimos 2,500.00 MXN.", EVIDENCE)
    assert not verdict.passed
    assert "2,500.00" in verdict.reason


def test_unknown_date_fails():
    verdict = check_amounts_dates_merchants("Llegará el 2026-10-15.", EVIDENCE)
    assert not verdict.passed


def test_slash_date_matches_either_reading():
    assert check_amounts_dates_merchants("Hecho el 28/09/2026.", EVIDENCE).passed
    assert not check_amounts_dates_merchants("Hecho el 15/10/2026.", EVIDENCE).passed


def test_unknown_quoted_merchant_fails():
    verdict = check_amounts_dates_merchants("El cargo es de «Coppel».", EVIDENCE)
    assert not verdict.passed
    assert "Coppel" in verdict.reason


def test_plain_numbers_without_currency_are_not_amount_claims():
    # A folio number is not an amount claim: no decimal part, no currency nearby.
    assert check_amounts_dates_merchants("Su folio es 12345.", EVIDENCE).passed


def test_stated_status_passes_when_it_matches_the_record():
    assert check_stated_status("Su pago sigue pendiente.", EVIDENCE).passed


def test_stated_status_fails_when_it_contradicts_the_record():
    verdict = check_stated_status("Su pago fue rechazado.", EVIDENCE)
    assert not verdict.passed
    assert "Declined" in verdict.reason


def test_reply_without_a_status_word_passes():
    assert check_stated_status("Estamos revisando su caso.", EVIDENCE).passed


def test_claimed_action_with_read_back_passes():
    assert check_claimed_actions_read_back("He cancelado su transferencia.", EVIDENCE).passed


def test_claimed_action_without_read_back_fails():
    evidence = Evidence(read_backs=frozenset())
    verdict = check_claimed_actions_read_back("Se canceló su transferencia.", evidence)
    assert not verdict.passed
    assert "cancel_transfer" in verdict.reason


def test_reply_claiming_no_action_passes():
    assert check_claimed_actions_read_back("Su pago sigue pendiente.", EVIDENCE).passed


def test_other_customer_data_fails():
    verdict = check_no_other_customer_data("El cliente CUST-777 ya lo recibió.", EVIDENCE)
    assert not verdict.passed
    # The reason names the count, never the leaked marker itself.
    assert "CUST-777" not in verdict.reason


def test_clean_reply_passes_the_privacy_check():
    assert check_no_other_customer_data("Su pago sigue pendiente.", EVIDENCE).passed


def test_spanish_reply_to_a_spanish_customer_passes():
    text = "Su pago está pendiente. Hemos revisado su cuenta, gracias por su paciencia."
    assert check_reply_language(text, EVIDENCE).passed


def test_portuguese_reply_to_a_spanish_customer_fails():
    evidence = Evidence(customer_language="es")
    verdict = check_reply_language(
        "Seu pagamento está na conta, você não precisa fazer nada, obrigado.", evidence
    )
    assert not verdict.passed
    assert "pt" in verdict.reason


def test_short_reply_without_markers_passes():
    assert check_reply_language("OK.", Evidence(customer_language="pt")).passed


def test_registry_covers_the_shipped_rubric_code_criteria():
    rubric = load_rubric()
    code_ids = {criterion.id for criterion in rubric.criteria_for(CheckerKind.CODE)}
    assert code_ids == set(CODE_CHECKS)


def test_run_code_checks_returns_one_verdict_per_code_criterion_in_order():
    rubric = load_rubric()
    verdicts = run_code_checks(rubric, "Su pago sigue pendiente.", EVIDENCE)
    assert [verdict.criterion_id for verdict in verdicts] == [
        criterion.id for criterion in rubric.criteria_for(CheckerKind.CODE)
    ]
    assert all(verdict.checker is CheckerKind.CODE for verdict in verdicts)


def test_a_code_criterion_without_a_check_fails_loudly():
    rubric = Rubric.model_validate(
        {
            "id": "r",
            "version": 1,
            "output_type": "customer_answer",
            "criteria": [
                {"id": "no-such-check", "text": "x", "checker": "code", "severity": "blocking"}
            ],
        }
    )
    with pytest.raises(KeyError, match="no-such-check"):
        run_code_checks(rubric, "texto", EVIDENCE)


@pytest.mark.parametrize(
    "reply",
    [
        "Le reembolsaremos el monto mañana.",
        "Recibirá su reembolso en 24 horas.",
        "Se le devolverá el dinero hoy.",
        "Acreditaremos 1,500.00 MXN en su cuenta.",
        "Garantizamos que no habrá cargos.",
        "Vamos reembolsar o valor amanhã.",
        "Será devolvido ainda hoje.",
        "Creditaremos o valor na sua conta.",
        "We will refund the amount tomorrow.",
        "The money will be credited by Friday.",
        "Recibirá un reembolso en las próximas horas.",
        "Va a recibir el reembolso hoy.",
        "Os valores serão estornados amanhã.",
        "We'll return the money by Friday.",
        "Le garantizo que no habrá cargos.",
    ],
)
def test_a_promise_of_money_moving_fails(reply):
    verdict = check_no_money_movement_promise(reply, EVIDENCE)
    assert not verdict.passed
    assert verdict.criterion_id == "no-money-movement-promise"
    assert verdict.checker is CheckerKind.CODE


@pytest.mark.parametrize(
    "reply",
    [
        "Su transferencia de 1,500.00 MXN está pendiente.",
        "Su pago fue revertida según el registro.",  # states a status, promises nothing
        "El monto fue reembolsado a su cuenta.",  # a fact about a Reversed payment, not a promise
        "El reembolso ya fue acreditado el 2026-06-12.",
        "No habrá reembolso para este pago.",  # a negation is honest
        "O valor foi estornado ontem.",
        "The refunded amount appears on your statement.",
        "Su pago foi recusado; posso tentar de novo se quiser.",
        "Una persona del equipo revisará su caso.",
    ],
)
def test_a_reply_that_states_facts_passes_the_promise_check(reply):
    assert check_no_money_movement_promise(reply, EVIDENCE).passed
