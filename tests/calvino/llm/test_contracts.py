"""Tests for the provider-agnostic chat interface (TSD-008).

Everything here runs without a network or a model.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from calvino.llm.contracts import (
    ChatRequest,
    ChatResponse,
    Message,
    MessageRole,
    Role,
    assert_distinct_families,
    model_family,
)
from calvino.llm.errors import LlmConfigurationError, LlmRule
from calvino.records import DecisionRecord, Versions


def test_request_needs_at_least_one_message():
    with pytest.raises(ValidationError):
        ChatRequest(role=Role.AGENT, messages=())


def test_request_refuses_unknown_fields():
    with pytest.raises(ValidationError):
        ChatRequest(
            role=Role.AGENT,
            messages=(Message(role=MessageRole.USER, content="hola"),),
            tools=[{"name": "cancel"}],
        )


def test_request_and_response_are_frozen(chat_request):
    request = chat_request("hola")
    response = ChatResponse(text="hi", model="fake-model")
    with pytest.raises(ValidationError):
        request.role = Role.JUDGE
    with pytest.raises(ValidationError):
        response.text = "tampered"


def test_empty_content_is_refused():
    with pytest.raises(ValidationError):
        Message(role=MessageRole.USER, content="")


def test_token_counts_and_latency_cannot_be_negative():
    with pytest.raises(ValidationError):
        ChatResponse(text="hi", model="fake-model", completion_tokens=-1)
    with pytest.raises(ValidationError):
        ChatResponse(text="hi", model="fake-model", latency_ms=-1.0)


def test_response_must_name_the_model_the_provider_reported():
    # The model id is what a replay names, so an empty one is not a usable answer.
    with pytest.raises(ValidationError):
        ChatResponse(text="hi", model="")


def test_temperature_outside_the_documented_range_is_refused():
    messages = (Message(role=MessageRole.USER, content="hola"),)
    with pytest.raises(ValidationError):
        ChatRequest(role=Role.AGENT, messages=messages, temperature=2.5)


def test_response_fits_a_decision_record():
    # Decision 20: the model version is recorded with every decision.
    response = ChatResponse(text="hi", model="Qwen/Qwen3.6-35B-A3B-FP8", completion_tokens=12)
    record = DecisionRecord(
        stage="verifier",
        session_ref="0" * 64,
        policy_version="v1",
        verdict="pass",
        latency_ms=response.latency_ms,
        versions=Versions(model=response.model),
    )
    assert record.versions.model == "Qwen/Qwen3.6-35B-A3B-FP8"


def test_fake_client_answers_per_purpose_and_records_requests(
    fake_chat_client_factory, chat_request
):
    fake = fake_chat_client_factory({"draft": "Your transfer is pending."}, default_reply="unused")

    draft = fake.complete(chat_request("hola", purpose="draft"))
    judge = fake.complete(chat_request("hola", role=Role.JUDGE, purpose="judge"))

    assert draft.text == "Your transfer is pending."
    assert judge.text == "unused"
    assert [request.role for request in fake.requests] == [Role.AGENT, Role.JUDGE]


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("Qwen/Qwen3.6-35B-A3B-FP8", "qwen"),
        ("Qwen3.8-27B", "qwen"),
        ("deepseek-chat", "deepseek"),
        ("  DeepSeek-R1  ", "deepseek"),
    ],
)
def test_model_family_reads_the_name_in_the_id(model, expected):
    assert model_family(model) == expected


def test_model_family_refuses_an_id_with_no_name():
    with pytest.raises(LlmConfigurationError):
        model_family("3.8-27B")


def test_judge_from_another_family_is_allowed():
    assert_distinct_families("Qwen/Qwen3.6-35B-A3B-FP8", "deepseek-chat")


@pytest.mark.parametrize("judge", ["Qwen3.8-27B", "Qwen/Qwen3.6-35B-A3B-FP8"])
def test_judge_from_the_agents_own_family_is_refused(judge):
    # Decision 20: a judge from the agent's family tends to pass its family's mistakes.
    with pytest.raises(LlmConfigurationError) as caught:
        assert_distinct_families("Qwen/Qwen3.6-35B-A3B-FP8", judge)
    assert caught.value.rule is LlmRule.SAME_FAMILY


def test_configuration_error_carries_its_rule_id():
    error = LlmConfigurationError("no key", rule=LlmRule.CONFIG)
    assert str(error).startswith("LLM-CONFIG:")
    assert error.rule is LlmRule.CONFIG


def test_message_roles_are_the_wire_names():
    assert [role.value for role in MessageRole] == ["system", "user", "assistant"]
