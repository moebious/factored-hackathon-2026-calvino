"""OpenAI-compatible chat completions adapter (TSD-008).

Talks to any endpoint that answers ``/chat/completions`` in the OpenAI shape, which is how the
language work reaches a provider: Hetzner's Inference API today, Hugging Face Inference Providers or
OpenRouter for the judge. Adding one is this class with a different ``base_url``, not a new adapter.

Three provider behaviours are handled here rather than in each caller: a request timeout, retries
for the failures worth retrying (429 and 5xx, never another 4xx, which is a request the caller got
wrong), and a client-side requests-per-window limiter so a demo paces itself instead of collecting
429s.

``httpx`` is used directly instead of a provider SDK: the wire format is small, and this way the
timeout, the retry rules and the limiter are ours and can be tested offline through an injected
transport. Tests never reach the network (AGENTS.md).

The key is read from the environment by the provider module and is never logged, never put in an
error message and never sent anywhere but the ``Authorization`` header.
"""

from __future__ import annotations

import os
import time
from collections import deque
from collections.abc import Callable, Mapping

import httpx

from calvino.llm.contracts import ChatRequest, ChatResponse
from calvino.llm.errors import (
    LlmConfigurationError,
    LlmError,
    LlmRateLimited,
    LlmResponseError,
    LlmRule,
    LlmTimeout,
    LlmTruncated,
    LlmUnavailable,
)

DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_RETRIES = 2
DEFAULT_BACKOFF_SECONDS = 0.5
# Providers cap calls per key over a window. Hetzner documents 10 requests per 60 s [vendor]; the
# default sits below that because one case costs an agent call and a judge call, so a demo would
# spend the whole allowance in a few cases.
DEFAULT_MAX_REQUESTS = 8
DEFAULT_WINDOW_SECONDS = 60.0

_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class RateLimiter:
    """At most ``limit`` acquisitions in ``window`` seconds, blocking for a free slot.

    The clock and the sleep are injected so tests can run a whole window instantly.
    """

    def __init__(
        self,
        limit: int,
        window: float = DEFAULT_WINDOW_SECONDS,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if limit < 1:
            raise LlmConfigurationError("a rate limiter needs a limit of at least one request")
        if window <= 0:
            raise LlmConfigurationError("a rate limiter needs a positive window")
        self._limit = limit
        self._window = window
        self._clock = clock
        self._sleep = sleep
        self._stamps: deque[float] = deque()

    def acquire(self) -> float:
        """Block until a slot is free; return how long it waited."""
        waited = 0.0
        now = self._clock()
        while self._stamps and now - self._stamps[0] >= self._window:
            self._stamps.popleft()
        if len(self._stamps) >= self._limit:
            waited = max(0.0, (self._stamps[0] + self._window) - now)
            if waited:
                self._sleep(waited)
                now = self._clock()
                while self._stamps and now - self._stamps[0] >= self._window:
                    self._stamps.popleft()
        self._stamps.append(now)
        return waited


class OpenAiCompatibleClient:
    """One chat model on one OpenAI-compatible endpoint."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        retries: int = DEFAULT_RETRIES,
        backoff: float = DEFAULT_BACKOFF_SECONDS,
        limiter: RateLimiter | None = None,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not base_url.startswith(("http://", "https://")):
            raise LlmConfigurationError("base_url must be an http or https URL")
        if not api_key:
            raise LlmConfigurationError("an API key is required and is never defaulted")
        if not model.strip():
            raise LlmConfigurationError(
                "a model id is required: the provider's /v1/models list is authoritative, "
                "so ids are configured, not hardcoded"
            )
        if retries < 0:
            raise LlmConfigurationError("retries cannot be negative")
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._retries = retries
        self._backoff = backoff
        self._limiter = limiter
        self._clock = clock
        self._sleep = sleep
        self._client = httpx.Client(
            base_url=self._base_url,
            timeout=timeout,
            transport=transport,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )

    @property
    def model(self) -> str:
        """The configured model id, for logs and configuration checks."""
        return self._model

    @property
    def base_url(self) -> str:
        """The endpoint root, so a configuration check can prove where traffic would go."""
        return self._base_url

    def list_models(self) -> tuple[str, ...]:
        """The provider's model ids. Authoritative: this is where a configured id is checked."""
        payload = self._send("GET", "/models")
        try:
            entries = payload["data"]
            ids = [str(entry["id"]) for entry in entries]
        except (KeyError, TypeError) as error:
            raise LlmResponseError("the models response has no usable 'data' list") from error
        return tuple(ids)

    def complete(self, request: ChatRequest) -> ChatResponse:
        """Ask the model for one completion. Raises ``LlmError`` with a stable id on any failure."""
        payload: dict[str, object] = {
            "model": self._model,
            "messages": [{"role": m.role.value, "content": m.content} for m in request.messages],
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.max_completion_tokens is not None:
            payload["max_completion_tokens"] = request.max_completion_tokens
        if request.seed is not None:
            payload["seed"] = request.seed
        if request.reasoning_effort is not None:
            payload["reasoning_effort"] = request.reasoning_effort.value

        started = self._clock()
        body = self._send("POST", "/chat/completions", payload)
        return _parse_completion(body, self._model, (self._clock() - started) * 1000.0)

    def _send(self, method: str, path: str, payload: dict[str, object] | None = None) -> dict:
        if self._limiter is not None:
            self._limiter.acquire()
        url = f"{self._base_url}{path}"
        last: LlmError | None = None
        cause: Exception | None = None
        for attempt in range(self._retries + 1):
            try:
                response = self._client.request(method, url, json=payload)
            except httpx.TimeoutException as error:
                last = LlmTimeout(f"the provider did not answer {path} within {self._timeout}s")
                cause = error
            except httpx.HTTPError as error:
                last = LlmUnavailable(f"the provider could not be reached for {path}")
                cause = error
            else:
                if response.status_code < 400:
                    return _json_object(response)
                last = _error_for(response, path)
                if response.status_code not in _RETRYABLE_STATUS:
                    raise last
                cause = None
            if attempt < self._retries:
                self._sleep(self._delay_for(attempt, last))
        raise last from cause

    def _delay_for(self, attempt: int, error: LlmError | None) -> float:
        # A provider that tells us when to come back is believed over our own backoff.
        if isinstance(error, LlmRateLimited) and error.retry_after is not None:
            return error.retry_after
        return self._backoff * (2**attempt)

    def close(self) -> None:
        self._client.close()


def _json_object(response: httpx.Response) -> dict:
    try:
        payload = response.json()
    except ValueError as error:
        raise LlmResponseError("the provider answered with something that is not JSON") from error
    if not isinstance(payload, dict):
        raise LlmResponseError("the provider answered with JSON that is not an object")
    return payload


def _error_for(response: httpx.Response, path: str) -> LlmError:
    # Only the status and the provider's own retry hint are kept: an error body can echo the
    # request, and the request holds the customer's redacted context.
    status = response.status_code
    if status == 429:
        return LlmRateLimited(
            f"the provider's rate limit was hit on {path}", retry_after=_retry_after(response)
        )
    if status in _RETRYABLE_STATUS:
        return LlmUnavailable(f"the provider answered {status} on {path}")
    return LlmError(LlmRule.REJECTED, f"the provider rejected the request with {status} on {path}")


def _retry_after(response: httpx.Response) -> float | None:
    raw = response.headers.get("Retry-After")
    if raw is None:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        # The header may be an HTTP date; we do not parse dates, we just wait the backoff.
        return None


def _parse_completion(body: dict, requested_model: str, latency_ms: float) -> ChatResponse:
    try:
        choice = body["choices"][0]
        message = choice["message"]
    except (KeyError, IndexError, TypeError) as error:
        raise LlmResponseError("the response carries no chat completion") from error

    finish_reason = choice.get("finish_reason")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        # A reasoning model spends its budget before it writes anything, and returns that
        # reasoning under its own key, so the completion arrives with no content at all. That is
        # the caller's budget, not a broken provider, and the message says so.
        if finish_reason == "length":
            raise LlmTruncated(
                "the provider used the whole token budget on reasoning and wrote no answer; "
                "raise max_tokens and call again"
            )
        raise LlmResponseError("the completion carries no text content")

    usage = body.get("usage") or {}
    if not isinstance(usage, dict):
        usage = {}
    # The provider's own model string wins: it is the version that answered, which is what a
    # replay needs to name.
    model = body.get("model")
    return ChatResponse(
        text=content,
        model=str(model) if isinstance(model, str) and model else requested_model,
        prompt_tokens=_count(usage.get("prompt_tokens")),
        completion_tokens=_count(usage.get("completion_tokens")),
        finish_reason=finish_reason if isinstance(finish_reason, str) else None,
        latency_ms=latency_ms,
    )


def _count(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def client_from_env(
    prefix: str = "CALVINO_LLM",
    *,
    env: Mapping[str, str] | None = None,
    base_url: str,
    default_max_requests: int = DEFAULT_MAX_REQUESTS,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    transport: httpx.BaseTransport | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> OpenAiCompatibleClient:
    """Build a client from ``<prefix>_API_KEY``, ``<prefix>_MODEL`` and two optional limits.

    The prefix is what makes a second provider a configuration change rather than a code change:
    the agent role reads ``CALVINO_LLM_*`` and the judge reads ``CALVINO_JUDGE_*``. Nothing is
    defaulted that the provider could get wrong: a missing key or model stops startup, because a
    silent default would send traffic somewhere nobody chose.
    """
    values = os.environ if env is None else env

    if not base_url:
        raise LlmConfigurationError(f"{prefix}_BASE_URL must be set to the provider's API root")

    token = values.get(f"{prefix}_API_KEY", "")
    if not token:
        raise LlmConfigurationError(
            f"{prefix}_API_KEY must be set; the client does not start without it"
        )

    model = values.get(f"{prefix}_MODEL", "")
    if not model.strip():
        raise LlmConfigurationError(
            f"{prefix}_MODEL must be set: the provider's /v1/models list is authoritative, so the "
            "model id is configured and never hardcoded"
        )

    max_requests = _positive_int(
        values.get(f"{prefix}_MAX_REQUESTS"), default_max_requests, f"{prefix}_MAX_REQUESTS"
    )
    request_timeout = _positive_float(
        values.get(f"{prefix}_TIMEOUT_SECONDS"), timeout, f"{prefix}_TIMEOUT_SECONDS"
    )

    return OpenAiCompatibleClient(
        base_url=base_url,
        api_key=token,
        model=model,
        timeout=request_timeout,
        limiter=RateLimiter(max_requests, DEFAULT_WINDOW_SECONDS, clock=clock, sleep=sleep),
        transport=transport,
        clock=clock,
        sleep=sleep,
    )


def _positive_int(raw: str | None, default: int, name: str) -> int:
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        raise LlmConfigurationError(f"{name} must be a whole number, got {raw!r}") from None
    if value < 1:
        raise LlmConfigurationError(f"{name} must be at least 1, got {value}")
    return value


def _positive_float(raw: str | None, default: float, name: str) -> float:
    if raw is None or raw.strip() == "":
        return default
    try:
        value = float(raw)
    except ValueError:
        raise LlmConfigurationError(f"{name} must be a number, got {raw!r}") from None
    if value <= 0:
        raise LlmConfigurationError(f"{name} must be greater than zero, got {value}")
    return value
