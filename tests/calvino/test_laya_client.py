"""Tests for LayaClient, question builders and answer parsing (TSD-005).

These run without laya installed: LayaClient gets a FakeRouter injected, and
the import guard is tested by pointing sys.modules at a failed import.
"""

import sys

import pytest
from pydantic import ValidationError

from calvino.classifiers import laya as laya_module
from calvino.classifiers.laya import (
    LayaAnswer,
    LayaClient,
    QuestionBuilder,
    clarity_question,
    injection_risk_question,
    intent_within_stuck_payment_question,
    needs_human_question,
    parse_answers,
    workflow_area_question,
    workflow_questions,
)


def test_question_builder_choice_valid():
    """QuestionBuilder.choice builds a laya 0.3.x choice definition."""
    q = QuestionBuilder.choice("Which?", {"a": "Option a.", "b": "Option b."})
    assert q["type"] == "choice"
    assert q["instructions"] == "Which?"
    assert q["criteria"] == {"a": "Option a.", "b": "Option b."}

    q = QuestionBuilder.choice("Which?", {c: f"Option {c}." for c in "abcdefghij"})
    assert len(q["criteria"]) == 10


def test_question_builder_choice_rejects_bad_option_counts():
    """Choice questions need 2-10 options."""
    with pytest.raises(ValueError, match="2-10 options"):
        QuestionBuilder.choice("Which?", {"only": "One option."})
    with pytest.raises(ValueError, match="2-10 options"):
        QuestionBuilder.choice("Which?", {c: f"Option {c}." for c in "abcdefghijk"})


def test_question_builder_choice_rejects_empty_text():
    """Instructions and option descriptions must not be empty."""
    with pytest.raises(ValueError, match="instructions"):
        QuestionBuilder.choice("   ", {"a": "A.", "b": "B."})
    with pytest.raises(ValueError, match="non-empty"):
        QuestionBuilder.choice("Which?", {"a": "", "b": "B."})


def test_question_builder_binary_needs_neutral_keys():
    """Binary questions reject yes/no-style keys (DESIGN 4.3 rule 5)."""
    q = QuestionBuilder.binary("Is it clear?", "clear", "Clear.", "unclear", "Unclear.")
    assert q["type"] == "choice"
    assert set(q["criteria"]) == {"clear", "unclear"}

    with pytest.raises(ValueError, match="neutral keys"):
        QuestionBuilder.binary("Is it clear?", "yes", "Yes.", "no", "No.")


def test_workflow_questions_obey_constraints():
    """The workflow question set obeys the usage rules."""
    questions = workflow_questions()
    assert set(questions) == {
        "workflow_area",
        "intent",
        "clear_enough",
        "needs_human",
        "injection",
    }
    for q in questions.values():
        assert q["type"] == "choice"
        assert 2 <= len(q["criteria"]) <= 10
    # The three binary questions use neutral two-option choices.
    for qid in ("clear_enough", "needs_human", "injection"):
        assert len(questions[qid]["criteria"]) == 2


def test_individual_builders_match_question_set():
    """The standalone builders return the same definitions as the set."""
    assert workflow_area_question() == workflow_questions()["workflow_area"]
    assert intent_within_stuck_payment_question() == workflow_questions()["intent"]
    assert clarity_question() == workflow_questions()["clear_enough"]
    assert needs_human_question() == workflow_questions()["needs_human"]
    assert injection_risk_question() == workflow_questions()["injection"]


def test_laya_answer_requires_probabilities_summing_to_one():
    """LayaAnswer validates that probabilities sum to 1 (small rounding slack)."""
    answer = LayaAnswer(
        question_id="q",
        chosen_option="a",
        probabilities={"a": 0.6, "b": 0.4},
        confidence=0.6,
    )
    assert answer.chosen_option == "a"

    # laya rounds to 4 decimals: 0.3333 * 3 = 0.9999 is acceptable.
    LayaAnswer(
        question_id="q",
        chosen_option="a",
        probabilities={"a": 0.3333, "b": 0.3333, "c": 0.3333},
        confidence=0.34,
    )

    with pytest.raises(ValidationError, match="sum to 1"):
        LayaAnswer(
            question_id="q",
            chosen_option="a",
            probabilities={"a": 0.5, "b": 0.4},
            confidence=0.5,
        )


def test_laya_answer_requires_chosen_option_among_probabilities():
    """The chosen option must be one of the probability keys."""
    with pytest.raises(ValidationError, match="not among the probabilities"):
        LayaAnswer(
            question_id="q",
            chosen_option="c",
            probabilities={"a": 0.5, "b": 0.5},
            confidence=0.5,
        )


def test_laya_answer_confidence_in_range():
    """Confidence must be between 0 and 1."""
    with pytest.raises(ValidationError):
        LayaAnswer(
            question_id="q",
            chosen_option="a",
            probabilities={"a": 0.6, "b": 0.4},
            confidence=1.1,
        )


def _choice_payload(qid="q", choice="a", probabilities=None, answer_confidence=0.9):
    """A laya 0.3.x-style predict payload for one choice answer."""
    probabilities = probabilities or {"a": 0.9, "b": 0.1}
    return {
        "answers": {
            qid: {
                "type": "choice",
                "choice": choice,
                "probabilities": probabilities,
                "confidence": 0.7,
                "answer_confidence": answer_confidence,
                "action": {"act_probability": 0.42},
            }
        },
        "usage": {"total_tokens": 123},
    }


def test_parse_answers_strips_act_probability():
    """parse_answers never exposes action.act_probability (DESIGN 4.3 rule 6)."""
    answers = parse_answers(_choice_payload())
    assert len(answers) == 1
    answer = answers[0]
    assert answer.question_id == "q"
    assert answer.chosen_option == "a"
    assert answer.probabilities == {"a": 0.9, "b": 0.1}
    # The gated confidence is laya's calibrated answer_confidence.
    assert answer.confidence == 0.9
    dumped = answer.model_dump()
    assert "action" not in dumped
    assert "act_probability" not in str(dumped)


def test_parse_answers_rejects_non_choice_types():
    """Calvino only asks choice questions; other answer types are a bug."""
    payload = _choice_payload()
    payload["answers"]["q"]["type"] = "noul"
    with pytest.raises(ValueError, match="unsupported laya answer type"):
        parse_answers(payload)


def test_parse_answers_empty_payload():
    """An empty answers dict parses to an empty list."""
    assert parse_answers({"answers": {}, "usage": {}}) == []


def test_client_classify_uses_injected_router(fake_router_factory):
    """classify passes state and questions to the router and parses the payload."""
    client = LayaClient()
    client._router = fake_router_factory(
        {"needs_human": {"human needed": 0.8, "can handle automatically": 0.2}}
    )
    questions = {"needs_human": needs_human_question()}

    answers = client.classify("Quiero hablar con una persona, por favor.", questions)

    assert len(answers) == 1
    assert answers[0].question_id == "needs_human"
    assert answers[0].chosen_option == "human needed"
    assert answers[0].confidence == 0.8
    state, sent_questions, model = client._router.calls[0]
    assert state == "Quiero hablar con una persona, por favor."
    assert sent_questions == questions
    assert model == "multilingual"


def test_client_classify_strips_act_probability(fake_router_factory):
    """The fake router returns act_probability; the client never exposes it."""
    client = LayaClient()
    client._router = fake_router_factory()

    answers = client.classify("mi transferencia no ha llegado", workflow_questions())

    assert len(answers) == 5
    for answer in answers:
        assert "act_probability" not in str(answer.model_dump())
        # Probabilities cover exactly the question's criteria keys.
        assert set(answer.probabilities) == set(
            workflow_questions()[answer.question_id]["criteria"]
        )


def test_client_preload_loads_pinned_model(fake_router_factory):
    """preload constructs the router once and preloads the pinned model."""
    client = LayaClient()
    router = fake_router_factory()
    client._router = router

    client.preload()
    client.preload()  # idempotent

    assert router.preloaded_models == ["multilingual"]


def test_client_preload_fails_fast_without_laya(monkeypatch):
    """preload raises a clear startup error when laya is not installed."""
    # sys.modules["laya"] = None makes `from laya import Router` raise ImportError.
    monkeypatch.setitem(sys.modules, "laya", None)
    client = LayaClient()

    with pytest.raises(RuntimeError, match="uv pip install laya"):
        client.preload()
    assert client._router is None


def test_client_classify_preloads_lazily(fake_router_factory, monkeypatch):
    """classify without an explicit preload loads the model first."""
    client = LayaClient()
    router = fake_router_factory()
    monkeypatch.setattr(laya_module, "_load_router", lambda: router)

    client.classify("hola", {"needs_human": needs_human_question()})

    assert router.preloaded_models == ["multilingual"]
    assert len(router.calls) == 1
