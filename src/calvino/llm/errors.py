"""Stable ids for every failure an LLM call can report (TSD-008).

Same idea as the tool refusals in ``calvino.tools.errors``: a failure always names the rule that
fired, so the hub can log it, the oracle can score it and a test can assert it. The ids are part
of the contract: add new ones, never rename.

A message never carries the prompt, the completion or the API key. A provider error page can echo
the request back, so provider text is not copied into the message either.
"""

from __future__ import annotations

from enum import StrEnum


class LlmRule(StrEnum):
    """The rule behind an LLM failure."""

    CONFIG = "LLM-CONFIG"
    # The judge would come from the same model family as the agent (decision 20).
    SAME_FAMILY = "LLM-SAME-FAMILY"
    RATE_LIMITED = "LLM-RATE-LIMITED"
    TIMEOUT = "LLM-TIMEOUT"
    UNAVAILABLE = "LLM-UNAVAILABLE"
    # The provider answered with something that is not a chat completion we can read.
    BAD_RESPONSE = "LLM-BAD-RESPONSE"
    # A 4xx that is not a rate limit: the request itself was wrong, so retrying it is pointless.
    REJECTED = "LLM-REJECTED"


class LlmError(Exception):
    """An LLM call failed; ``rule`` says why."""

    def __init__(self, rule: LlmRule, message: str) -> None:
        super().__init__(f"{rule.value}: {message}")
        self.rule = rule
        self.message = message


class LlmConfigurationError(LlmError):
    """The client is misconfigured and must not start (a missing key, a same-family judge)."""

    def __init__(self, message: str, *, rule: LlmRule = LlmRule.CONFIG) -> None:
        super().__init__(rule, message)


class LlmRateLimited(LlmError):
    """The provider's rate limit was hit and stayed hit through the retries.

    ``retry_after`` is the provider's own hint when it sent one, so the hub can tell a waiting
    customer when to come back instead of guessing.
    """

    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(LlmRule.RATE_LIMITED, message)
        self.retry_after = retry_after


class LlmTimeout(LlmError):
    """The provider did not answer within the request timeout."""

    def __init__(self, message: str) -> None:
        super().__init__(LlmRule.TIMEOUT, message)


class LlmUnavailable(LlmError):
    """The provider failed or was unreachable (a transport error or a 5xx)."""

    def __init__(self, message: str) -> None:
        super().__init__(LlmRule.UNAVAILABLE, message)


class LlmResponseError(LlmError):
    """The provider answered, but not with a chat completion we can read."""

    def __init__(self, message: str) -> None:
        super().__init__(LlmRule.BAD_RESPONSE, message)
