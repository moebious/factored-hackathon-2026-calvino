"""Tests for the Hetzner provider configuration (TSD-008).

The environment is passed in explicitly, so nothing here reads the developer's own variables and no
test needs a token.
"""

from __future__ import annotations

import httpx
import pytest

from calvino.llm.contracts import ChatRequest, Message, MessageRole, Role
from calvino.llm.errors import LlmConfigurationError, LlmError, LlmRule
from calvino.llm.hetzner import (
    HETZNER_BASE_URL,
    HETZNER_REQUESTS_PER_WINDOW,
    HETZNER_SAFE_REQUESTS_PER_WINDOW,
    clients_from_env,
    hetzner_client_from_env,
    judge_client_from_env,
)

AGENT_MODEL = "Qwen/Qwen3.6-35B-A3B-FP8"
JUDGE_MODEL = "deepseek-chat"

# Values, not credentials: the guard in .githooks/pre-commit reads key-shaped assignments, and
# nothing here is a secret.
AGENT_ENV = {
    "CALVINO_LLM_API_KEY": "unit-test-agent-value",
    "CALVINO_LLM_MODEL": AGENT_MODEL,
}
JUDGE_ENV = {
    "CALVINO_JUDGE_API_KEY": "unit-test-judge-value",
    "CALVINO_JUDGE_MODEL": JUDGE_MODEL,
    "CALVINO_JUDGE_BASE_URL": "https://router.example/api/v1",
}


def ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"model": "m", "choices": [{"message": {"content": "ok"}}]})


def test_the_agent_client_points_at_hetzner_by_default():
    client = hetzner_client_from_env(env=AGENT_ENV)
    assert client.model == AGENT_MODEL


def test_the_base_url_defaults_to_hetzner_and_can_be_overridden():
    assert hetzner_client_from_env(env=AGENT_ENV).base_url == HETZNER_BASE_URL
    assert HETZNER_BASE_URL == "https://inference.hetzner.com/api/v1"

    overridden = hetzner_client_from_env(
        env={**AGENT_ENV, "CALVINO_LLM_BASE_URL": "https://proxy.example/api/v1"}
    )
    assert overridden.base_url == "https://proxy.example/api/v1"


def test_the_pacing_default_sits_below_the_documented_cap():
    assert HETZNER_SAFE_REQUESTS_PER_WINDOW < HETZNER_REQUESTS_PER_WINDOW
    assert HETZNER_REQUESTS_PER_WINDOW == 10


def test_the_agent_client_calls_the_hetzner_path(chat_request):
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return ok(request)

    hetzner_client_from_env(env=AGENT_ENV, transport=httpx.MockTransport(handler)).complete(
        chat_request("hola")
    )
    assert seen == ["https://inference.hetzner.com/api/v1/chat/completions"]


def test_a_missing_token_stops_startup():
    with pytest.raises(LlmConfigurationError) as caught:
        hetzner_client_from_env(env={"CALVINO_LLM_MODEL": AGENT_MODEL})
    assert "CALVINO_LLM_API_KEY" in str(caught.value)


def test_a_missing_model_stops_startup_and_says_why_it_is_not_defaulted():
    with pytest.raises(LlmConfigurationError) as caught:
        hetzner_client_from_env(env={"CALVINO_LLM_API_KEY": "unit-test-value"})
    message = str(caught.value)
    assert "CALVINO_LLM_MODEL" in message
    assert "/v1/models" in message


class FakeClock:
    """A monotonic clock that only moves when something sleeps."""

    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def test_the_request_cap_is_configurable(chat_request):
    clock = FakeClock()
    client = hetzner_client_from_env(
        env={**AGENT_ENV, "CALVINO_LLM_MAX_REQUESTS": "2"},
        transport=httpx.MockTransport(ok),
        clock=clock,
        sleep=clock.sleep,
    )
    for _ in range(3):
        client.complete(chat_request("hola"))
    # Two calls are free, the third waits a window instead of racing the provider's cap.
    assert clock.slept == [60.0]


@pytest.mark.parametrize(
    "overrides",
    [
        {"CALVINO_LLM_MAX_REQUESTS": "not-a-number"},
        {"CALVINO_LLM_MAX_REQUESTS": "0"},
    ],
)
def test_a_nonsense_request_cap_is_refused(overrides):
    with pytest.raises(LlmConfigurationError) as caught:
        hetzner_client_from_env(env={**AGENT_ENV, **overrides})
    assert "CALVINO_LLM_MAX_REQUESTS" in str(caught.value)


def test_the_timeout_is_configurable():
    assert (
        hetzner_client_from_env(
            env={**AGENT_ENV, "CALVINO_LLM_TIMEOUT_SECONDS": "12.5"},
        )
        is not None
    )
    with pytest.raises(LlmConfigurationError) as caught:
        hetzner_client_from_env(env={**AGENT_ENV, "CALVINO_LLM_TIMEOUT_SECONDS": "-1"})
    assert "CALVINO_LLM_TIMEOUT_SECONDS" in str(caught.value)


def test_the_retry_count_is_configurable_and_zero_means_a_single_attempt(chat_request):
    """Zero is the setting that matters: retrying a queueing provider makes a slow answer slower.

    A provider that answers in 6 s or fails outright is what we have measured, so the lever for a
    slow endpoint is fewer attempts, not a longer timeout.
    """
    attempts: list[httpx.Request] = []

    def busy(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        return httpx.Response(503, json={"error": "busy"})

    def build(retries: str) -> object:
        return hetzner_client_from_env(
            env={**AGENT_ENV, "CALVINO_LLM_RETRIES": retries},
            transport=httpx.MockTransport(busy),
            sleep=lambda _: None,
        )

    with pytest.raises(LlmError):
        build("0").complete(chat_request("hola"))
    assert len(attempts) == 1, "retries=0 must not retry a 503"

    attempts.clear()
    with pytest.raises(LlmError):
        build("2").complete(chat_request("hola"))
    assert len(attempts) == 3, "retries=2 means the first attempt plus two retries"


@pytest.mark.parametrize("raw", ["-1", "not-a-number"])
def test_a_nonsense_retry_count_is_refused(raw):
    with pytest.raises(LlmConfigurationError) as caught:
        hetzner_client_from_env(env={**AGENT_ENV, "CALVINO_LLM_RETRIES": raw})
    assert "CALVINO_LLM_RETRIES" in str(caught.value)


def test_the_retry_count_defaults_to_two():
    """An unconfigured role keeps the documented default, so nothing changes silently."""
    attempts: list[httpx.Request] = []

    def busy(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        return httpx.Response(503, json={"error": "busy"})

    client = hetzner_client_from_env(
        env=AGENT_ENV, transport=httpx.MockTransport(busy), sleep=lambda _: None
    )
    with pytest.raises(LlmError):
        client.complete(
            ChatRequest(role=Role.AGENT, messages=(Message(role=MessageRole.USER, content="hola"),))
        )
    assert len(attempts) == 3


def test_both_roles_are_built_from_one_call(chat_request):
    clients = clients_from_env(
        env={**AGENT_ENV, **JUDGE_ENV},
        agent_transport=httpx.MockTransport(ok),
        judge_transport=httpx.MockTransport(ok),
    )
    assert (clients.agent_model, clients.judge_model) == (AGENT_MODEL, JUDGE_MODEL)
    assert clients.agent.complete(chat_request("hola")).text == "ok"
    assert clients.judge.complete(chat_request("hola", role="judge")).text == "ok"


def test_a_judge_on_the_agents_own_provider_is_refused():
    # Decision 20: Hetzner serves Qwen only, so a judge pointed at it loses the independence the
    # decision asks for. The guard is a startup check, not a comment.
    with pytest.raises(LlmConfigurationError) as caught:
        clients_from_env(
            env={
                **AGENT_ENV,
                "CALVINO_JUDGE_API_KEY": "unit-test-judge-value",
                "CALVINO_JUDGE_MODEL": "Qwen3.8-27B",
                "CALVINO_JUDGE_BASE_URL": HETZNER_BASE_URL,
            }
        )
    assert caught.value.rule is LlmRule.SAME_FAMILY


def test_a_judge_with_no_base_url_is_told_which_variable_is_missing():
    with pytest.raises(LlmConfigurationError) as caught:
        clients_from_env(
            env={
                **AGENT_ENV,
                "CALVINO_JUDGE_API_KEY": "unit-test-judge-value",
                "CALVINO_JUDGE_MODEL": JUDGE_MODEL,
            }
        )
    assert "CALVINO_JUDGE_BASE_URL" in str(caught.value)


def test_the_judge_client_can_be_built_on_its_own():
    """The two roles are configured and rolled out independently."""
    judge = judge_client_from_env(env=JUDGE_ENV)
    assert judge.model == JUDGE_MODEL
    assert judge.base_url == "https://router.example/api/v1"


def test_the_judge_client_still_fails_closed_without_its_variables():
    with pytest.raises(LlmConfigurationError):
        judge_client_from_env(env={"CALVINO_LLM_API_KEY": "unit-test-agent-value"})


def test_the_agent_can_be_built_without_the_judge_being_configured():
    client = hetzner_client_from_env(env=AGENT_ENV)
    assert client.model == AGENT_MODEL
