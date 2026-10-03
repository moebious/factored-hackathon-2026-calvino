"""Tests for the OpenAI-compatible adapter (TSD-008).

Every test drives an injected ``httpx.MockTransport`` and an injected clock, so the suite runs
offline and a whole rate-limit window takes microseconds.
"""

from __future__ import annotations

import json

import httpx
import pytest

from calvino.llm.contracts import Message, MessageRole, Role
from calvino.llm.errors import (
    LlmConfigurationError,
    LlmError,
    LlmRateLimited,
    LlmResponseError,
    LlmRule,
    LlmTimeout,
    LlmUnavailable,
)
from calvino.llm.openai_compat import OpenAiCompatibleClient, RateLimiter

BASE_URL = "https://inference.example/api/v1"
TEST_TOKEN = "unit-test-value-not-a-real-credential"
MODEL = "Qwen/Qwen3.6-35B-A3B-FP8"


class FakeClock:
    """A monotonic clock that only moves when something sleeps."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def completion(
    content: str = "Your transfer is pending.",
    *,
    model: str = MODEL,
    finish_reason: str = "stop",
    usage: dict | None = None,
) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "model": model,
            "choices": [
                {
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": finish_reason,
                }
            ],
            "usage": usage or {"prompt_tokens": 31, "completion_tokens": 7},
        },
    )


def client_with(handler, **kwargs) -> OpenAiCompatibleClient:
    clock = FakeClock()
    client = OpenAiCompatibleClient(
        base_url=BASE_URL,
        api_key=TEST_TOKEN,
        model=MODEL,
        transport=httpx.MockTransport(handler),
        clock=clock,
        sleep=clock.sleep,
        **kwargs,
    )
    client.fake_clock = clock  # type: ignore[attr-defined]
    return client


def test_request_carries_the_model_the_messages_and_a_bearer_token(chat_request):
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return completion()

    client = client_with(handler)
    request = chat_request("Where is my transfer?")
    response = client.complete(request)

    sent = seen[0]
    assert sent.method == "POST"
    assert str(sent.url) == f"{BASE_URL}/chat/completions"
    assert sent.headers["authorization"] == f"Bearer {TEST_TOKEN}"
    body = json.loads(sent.content)
    assert body["model"] == MODEL
    assert body["messages"] == [{"role": "user", "content": "Where is my transfer?"}]
    # The purpose tag is for our logs, never the provider's.
    assert "purpose" not in body
    assert response.text == "Your transfer is pending."


def test_optional_sampling_fields_are_sent_only_when_set(chat_request):
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return completion()

    client = client_with(handler)
    client.complete(chat_request("hola"))
    assert "temperature" not in seen[0]
    assert "max_tokens" not in seen[0]

    client.complete(chat_request("hola").model_copy(update={"temperature": 0.2, "max_tokens": 256}))
    assert seen[1]["temperature"] == 0.2
    assert seen[1]["max_tokens"] == 256


def test_response_carries_the_reported_model_usage_and_latency(chat_request):
    def handler(request: httpx.Request) -> httpx.Response:
        return completion(model="Qwen/Qwen3.8-27B", finish_reason="length")

    client = client_with(handler)
    response = client.complete(chat_request("hola"))

    # The provider's model string wins over what we asked for: that is the version that answered.
    assert response.model == "Qwen/Qwen3.8-27B"
    assert client.model == MODEL
    assert (response.prompt_tokens, response.completion_tokens) == (31, 7)
    assert response.finish_reason == "length"
    assert response.latency_ms >= 0


def test_missing_usage_counts_as_zero_rather_than_failing(chat_request):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"model": MODEL, "choices": [{"message": {"content": "ok"}}]}
        )

    client = client_with(handler)
    response = client.complete(chat_request("hola"))
    assert (response.prompt_tokens, response.completion_tokens) == (0, 0)
    assert response.finish_reason is None


def test_a_429_is_retried_and_then_reported_with_the_providers_hint(chat_request):
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) < 3:
            return httpx.Response(429, headers={"Retry-After": "2"})
        return completion()

    client = client_with(handler, retries=2, backoff=0.5)
    response = client.complete(chat_request("hola"))

    assert response.text == "Your transfer is pending."
    assert len(calls) == 3
    # Retry-After is believed over our own backoff.
    assert client.fake_clock.slept == [2.0, 2.0]


def test_a_429_that_never_clears_raises_the_rate_limit_error(chat_request):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "1"})

    client = client_with(handler, retries=1, backoff=0.5)
    with pytest.raises(LlmRateLimited) as caught:
        client.complete(chat_request("hola"))
    assert caught.value.rule is LlmRule.RATE_LIMITED
    assert caught.value.retry_after == 1.0
    # Three attempts: the first plus one retry.
    assert client.fake_clock.slept == [1.0]


def test_a_5xx_is_retried_with_exponential_backoff(chat_request):
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503) if len(calls) == 1 else completion()

    client = client_with(handler, retries=2, backoff=0.5)
    assert client.complete(chat_request("hola")).text
    assert client.fake_clock.slept == [0.5]


def test_a_5xx_that_persists_raises_unavailable(chat_request):
    client = client_with(lambda request: httpx.Response(500), retries=1, backoff=0.25)
    with pytest.raises(LlmUnavailable):
        client.complete(chat_request("hola"))


def test_a_400_is_not_retried(chat_request):
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(400, json={"error": {"message": "bad model"}})

    client = client_with(handler, retries=3, backoff=0.5)
    with pytest.raises(LlmError) as caught:
        client.complete(chat_request("hola"))
    assert caught.value.rule is LlmRule.REJECTED
    # Retrying a request the caller got wrong only spends the allowance.
    assert len(calls) == 1
    assert client.fake_clock.slept == []


def test_a_provider_error_body_is_not_echoed_into_the_message(chat_request):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400, json={"error": {"message": "context: card 4111111111111111 for Ana"}}
        )

    client = client_with(handler)
    with pytest.raises(LlmError) as caught:
        client.complete(chat_request("hola"))
    assert "4111111111111111" not in str(caught.value)


def test_a_timeout_is_retried_and_then_raises_the_timeout_error(chat_request):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    client = client_with(handler, retries=1, backoff=0.5)
    with pytest.raises(LlmTimeout) as caught:
        client.complete(chat_request("hola"))
    assert caught.value.rule is LlmRule.TIMEOUT


def test_an_unreachable_provider_raises_unavailable(chat_request):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host", request=request)

    client = client_with(handler, retries=0)
    with pytest.raises(LlmUnavailable):
        client.complete(chat_request("hola"))


def test_a_reply_that_is_not_json_raises_a_response_error(chat_request):
    client = client_with(lambda request: httpx.Response(200, text="<html>gateway</html>"))
    with pytest.raises(LlmResponseError):
        client.complete(chat_request("hola"))


@pytest.mark.parametrize(
    "body",
    [
        {"model": MODEL},
        {"model": MODEL, "choices": []},
        {"model": MODEL, "choices": [{"message": {"content": 42}}]},
    ],
)
def test_a_reply_without_readable_content_raises_a_response_error(chat_request, body):
    client = client_with(lambda request: httpx.Response(200, json=body))
    with pytest.raises(LlmResponseError):
        client.complete(chat_request("hola"))


def test_list_models_returns_the_providers_ids():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == f"{BASE_URL}/models"
        return httpx.Response(200, json={"data": [{"id": "Qwen3.8-27B"}, {"id": MODEL}]})

    assert client_with(handler).list_models() == ("Qwen3.8-27B", MODEL)


def test_list_models_refuses_a_reply_it_cannot_read():
    client = client_with(lambda request: httpx.Response(200, json={"object": "list"}))
    with pytest.raises(LlmResponseError):
        client.list_models()


def test_the_key_is_never_in_an_error_message(chat_request):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    client = client_with(handler)
    with pytest.raises(LlmError) as caught:
        client.complete(chat_request("hola"))
    assert TEST_TOKEN not in str(caught.value)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"base_url": "inference.example/api/v1"},
        {"api_key": ""},
        {"model": "  "},
        {"retries": -1},
    ],
)
def test_a_misconfigured_client_refuses_to_be_built(kwargs):
    settings = {"base_url": BASE_URL, "api_key": TEST_TOKEN, "model": MODEL, **kwargs}
    with pytest.raises(LlmConfigurationError):
        OpenAiCompatibleClient(**settings)


def test_the_limiter_paces_calls_over_a_window(chat_request):
    """A demo must not spend the provider's whole allowance in three cases."""
    clock = FakeClock()
    limiter = RateLimiter(2, 60.0, clock=clock, sleep=clock.sleep)
    client = client_with(lambda request: completion(), limiter=limiter)

    for _ in range(2):
        client.complete(chat_request("hola"))
    assert clock.slept == []

    # The third call waits for the first slot to leave the window.
    assert client.complete(chat_request("hola")) is not None
    assert clock.slept == [60.0]


def test_the_limiter_refuses_a_nonsense_configuration():
    with pytest.raises(LlmConfigurationError):
        RateLimiter(0)
    with pytest.raises(LlmConfigurationError):
        RateLimiter(1, window=0)


def test_system_and_assistant_turns_keep_their_wire_names(chat_request):
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return completion()

    client = client_with(handler)
    client.complete(
        chat_request("hola").model_copy(
            update={
                "messages": (
                    Message(role=MessageRole.SYSTEM, content="You are a bank agent."),
                    Message(role=MessageRole.USER, content="Where is my transfer?"),
                    Message(role=MessageRole.ASSISTANT, content="It is pending."),
                ),
                "role": Role.JUDGE,
            }
        )
    )
    assert [turn["role"] for turn in seen[0]["messages"]] == ["system", "user", "assistant"]
