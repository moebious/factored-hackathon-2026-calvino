"""Tests for the Laya check interface (TSD-004): scripted verdicts and call recording."""

from calvino.verifier.evidence import Evidence
from calvino.verifier.laya_checks import FakeLayaChecker
from calvino.verifier.rubric import CheckerKind, load_rubric

EVIDENCE = Evidence(customer_language="es")


def _laya_criteria():
    return load_rubric().criteria_for(CheckerKind.LAYA)


def test_fake_returns_scripted_verdicts_and_records_calls():
    fake = FakeLayaChecker(
        verdicts={"no-money-movement-promise": (False, "promises a refund")},
        default=(True, "grounded"),
    )
    criteria = _laya_criteria()
    verdicts = fake.check("Le reembolsaremos mañana.", EVIDENCE, criteria)
    assert fake.calls == [[c.id for c in criteria]]
    by_id = {v.criterion_id: v for v in verdicts}
    assert not by_id["no-money-movement-promise"].passed
    assert by_id["no-money-movement-promise"].reason == "promises a refund"
    assert by_id["factual-claims-grounded"].passed
    assert all(v.checker is CheckerKind.LAYA for v in verdicts)


def test_fake_default_passes_unscripted_criteria():
    fake = FakeLayaChecker()
    verdicts = fake.check("texto", EVIDENCE, _laya_criteria())
    assert all(v.passed for v in verdicts)
    assert all(v.checker is CheckerKind.LAYA for v in verdicts)
