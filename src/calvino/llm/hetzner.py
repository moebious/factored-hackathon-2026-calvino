"""Hetzner's Inference API as the agent-role provider (TSD-008).

Hetzner serves open-weight models over an OpenAI-compatible REST API at
``https://inference.hetzner.com/api/v1``. It is the cheapest way to put a Qwen model behind the
agent role (decision 20) and it needs no account beyond a token, which is what the roadmap was
waiting on for T-106 and T-301.

What its documentation states `[vendor]`, as of 2026-07-24:

- an OpenAI-compatible ``/v1/models``, ``/v1/completions`` and ``/v1/chat/completions``, so
  ``OpenAiCompatibleClient`` speaks it unchanged;
- the model list is definitive and will change during the experimental phase, so no model id is
  hardcoded here; check ``CALVINO_LLM_MODEL`` against ``client.list_models()``;
- 10 requests per 60 s per key, 4M input and 100k output tokens per 60 s, HTTP 429 when exceeded;
- free while experimental, offered "as is", with no SLA, no backups, and explicitly not for
  production. Content is not stored; usage timestamps and token counts are.

That last point is why the judge is not configured here. Hetzner serves Qwen only, and a judge
from the agent's own family tends to pass its family's mistakes (decision 20), so the judge reads
``CALVINO_JUDGE_*`` from a second provider and ``clients_from_env`` refuses the pair if the two
models turn out to share a family.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Mapping

import httpx

from calvino.llm.contracts import ChatClient, assert_distinct_families
from calvino.llm.openai_compat import OpenAiCompatibleClient, client_from_env

HETZNER_BASE_URL = "https://inference.hetzner.com/api/v1"

# The documented cap, and what we actually allow. One below the cap is not enough: a case costs an
# agent call and a judge call, so a demo would otherwise hit 429 mid-presentation.
HETZNER_REQUESTS_PER_WINDOW = 10
HETZNER_SAFE_REQUESTS_PER_WINDOW = 8

AGENT_ENV_PREFIX = "CALVINO_LLM"
JUDGE_ENV_PREFIX = "CALVINO_JUDGE"


def hetzner_client_from_env(
    *,
    env: Mapping[str, str] | None = None,
    transport: httpx.BaseTransport | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> OpenAiCompatibleClient:
    """The agent-role client, configured from ``CALVINO_LLM_*``.

    ``CALVINO_LLM_API_KEY`` and ``CALVINO_LLM_MODEL`` are required; the base URL defaults to
    Hetzner's and can be pointed elsewhere with ``CALVINO_LLM_BASE_URL``.
    ``CALVINO_LLM_MAX_REQUESTS`` and ``CALVINO_LLM_TIMEOUT_SECONDS`` override the pacing and the
    timeout.
    """
    values = os.environ if env is None else env
    return client_from_env(
        AGENT_ENV_PREFIX,
        env=values,
        base_url=values.get(f"{AGENT_ENV_PREFIX}_BASE_URL") or HETZNER_BASE_URL,
        default_max_requests=HETZNER_SAFE_REQUESTS_PER_WINDOW,
        transport=transport,
        clock=clock,
        sleep=sleep,
    )


def judge_client_from_env(
    *,
    env: Mapping[str, str] | None = None,
    transport: httpx.BaseTransport | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> OpenAiCompatibleClient:
    """The judge-role client, configured from ``CALVINO_JUDGE_*``.

    Separate from ``clients_from_env`` on purpose: the two roles are configured and can be
    rolled out independently, so a deployment that has the agent live and the judge not yet
    must still be able to check the agent against its provider's catalogue.
    """
    values = os.environ if env is None else env
    return client_from_env(
        JUDGE_ENV_PREFIX,
        env=values,
        base_url=values.get(f"{JUDGE_ENV_PREFIX}_BASE_URL", ""),
        transport=transport,
        clock=clock,
        sleep=sleep,
    )


class LlmClients:
    """The two role clients, built once at startup."""

    def __init__(self, agent: ChatClient, judge: ChatClient, agent_model: str, judge_model: str):
        self.agent = agent
        self.judge = judge
        self.agent_model = agent_model
        self.judge_model = judge_model


def clients_from_env(
    *,
    env: Mapping[str, str] | None = None,
    agent_transport: httpx.BaseTransport | None = None,
    judge_transport: httpx.BaseTransport | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> LlmClients:
    """Build the agent client on Hetzner and the judge client on a second provider.

    Refuses to return when the two models share a family, so decision 20's judge independence
    cannot be lost by editing one environment variable.
    """
    values = os.environ if env is None else env
    agent = hetzner_client_from_env(env=values, transport=agent_transport, clock=clock, sleep=sleep)
    judge = judge_client_from_env(env=values, transport=judge_transport, clock=clock, sleep=sleep)
    assert_distinct_families(agent.model, judge.model)
    return LlmClients(agent, judge, agent.model, judge.model)
