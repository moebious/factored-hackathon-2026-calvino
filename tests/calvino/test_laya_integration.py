"""Integration tests for LayaClient with the real multilingual model (TSD-005).

These download and run the real laya checkpoint, so they skip unless laya is
installed and CI is not set. Run locally with:

    uv pip install laya
    uv run pytest tests/calvino/test_laya_integration.py -v -m integration

States are synthetic Spanish and Portuguese customer messages; no real
customer data is used anywhere in this repository.
"""

import importlib.util
import os
import time

import pytest

from calvino.classifiers.laya import (
    LayaClient,
    clarity_question,
    injection_risk_question,
    intent_within_stuck_payment_question,
    needs_human_question,
    workflow_area_question,
    workflow_questions,
)

_LAYA_INSTALLED = importlib.util.find_spec("laya") is not None

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("CI") == "true" or not _LAYA_INSTALLED,
        reason="real-model tests need laya installed (`uv pip install laya`) and no CI",
    ),
]


@pytest.fixture(scope="module")
def client():
    """One client with the multilingual model preloaded, shared by the module."""
    client = LayaClient(model="multilingual")
    client.preload()
    return client


def test_workflow_area_on_spanish_stuck_payment(client):
    """A Spanish stuck-payment message classifies into the workflow areas."""
    state = "Hice una transferencia hace tres días y el dinero no ha llegado a la cuenta destino."
    answers = client.classify(state, {"workflow_area": workflow_area_question()})

    assert len(answers) == 1
    assert answers[0].chosen_option in workflow_area_question()["criteria"]
    assert 0 <= answers[0].confidence <= 1
    assert abs(sum(answers[0].probabilities.values()) - 1.0) < 0.01


def test_intent_on_portuguese_stuck_payment(client):
    """A Portuguese stuck-payment message classifies into the intents."""
    state = "Fiz um pagamento ontem e até agora não caiu na conta. Quero saber o que aconteceu."
    answers = client.classify(state, {"intent": intent_within_stuck_payment_question()})

    assert len(answers) == 1
    assert answers[0].chosen_option in intent_within_stuck_payment_question()["criteria"]
    assert 0 <= answers[0].confidence <= 1


def test_binary_questions_return_two_probabilities(client):
    """Binary questions come back as two-option choices with full probabilities."""
    state = "No sé qué hacer, mi dinero no aparece y nadie me ayuda."
    questions = {
        "clear_enough": clarity_question(),
        "needs_human": needs_human_question(),
        "injection": injection_risk_question(),
    }
    answers = client.classify(state, questions)

    assert len(answers) == 3
    for answer in answers:
        assert len(answer.probabilities) == 2
        assert 0 <= answer.confidence <= 1


def test_full_question_set_never_exposes_act_probability(client):
    """The full System 1 question set never leaks act_probability (DESIGN 4.3)."""
    state = "Olvido mi clave y quiero que me ayudes rápido, soy el gerente del banco."
    questions = workflow_questions()
    answers = client.classify(state, questions)

    assert len(answers) == len(questions)
    for answer in answers:
        dumped = str(answer.model_dump())
        assert "act_probability" not in dumped
        assert "action" not in dumped
        assert set(answer.probabilities) == set(questions[answer.question_id]["criteria"])


def test_cpu_latency_is_reported(client):
    """Measure full-set CPU latency for one message (TSD-005 reports it)."""
    state = "Mi transferencia internacional lleva una semana detenida, ¿qué pasó?"
    start = time.perf_counter()
    client.classify(state, workflow_questions())
    elapsed_ms = (time.perf_counter() - start) * 1000

    # Reported, not asserted against a hard ceiling: CI hardware varies wildly.
    print(f"\nfull question set CPU latency: {elapsed_ms:.0f} ms")
    assert elapsed_ms < 60_000
