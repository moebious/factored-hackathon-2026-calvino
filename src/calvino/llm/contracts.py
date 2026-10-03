"""The provider-agnostic chat interface (TSD-008).

The seam every language call in Calvino goes through. Nothing here knows about a provider, a
transport or a model id, so swapping providers is a constructor call and not a code change, and a
test can stand in for a model without one.

It decides nothing: the language model writes text, the policy (TSD-001) decides. The two roles
below exist because decision 20 requires them to be different models: a ``judge`` from the same
family as the ``agent`` tends to pass its family's mistakes, so ``assert_distinct_families``
refuses to build that pair.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from calvino.llm.errors import LlmConfigurationError, LlmRule


class Role(StrEnum):
    """Which job the model is doing. Decision 20 pins a different family per role."""

    AGENT = "agent"
    JUDGE = "judge"


class MessageRole(StrEnum):
    """Who is speaking in a request, as the OpenAI-compatible wire format names it."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ReasoningEffort(StrEnum):
    """How hard a reasoning model should think, in the vocabulary the providers publish."""

    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Message(BaseModel):
    """One turn. Content is text only; images and tool calls are out of scope in TSD-008."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    role: MessageRole
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    """One call. ``purpose`` is a free tag for logs and tests, never shown to the provider."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    role: Role
    messages: tuple[Message, ...] = Field(min_length=1)
    purpose: str | None = None
    # Left unset by default so each provider applies its own default rather than ours.
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1)
    # Providers disagree on the output-limit field name: the older ones take ``max_tokens`` and the
    # newer ones reject it in favour of ``max_completion_tokens``. Both are explicit and only one
    # may be set, so the request says which dialect it is written for instead of the adapter
    # guessing per provider.
    max_completion_tokens: int | None = Field(default=None, ge=1)
    # A fixed seed is what makes a repeated evaluation run comparable (T-303), so it is part of the
    # contract rather than something each caller remembers to pass.
    seed: int | None = None
    # Reasoning effort, for the reasoning models. The judge runs low: a criteria rubric is not hard
    # maths, and long reasoning tokens cost latency on a turn the customer is waiting for.
    reasoning_effort: ReasoningEffort | None = None

    @model_validator(mode="after")
    def _one_output_limit(self) -> ChatRequest:
        if self.max_tokens is not None and self.max_completion_tokens is not None:
            raise ValueError(
                "set max_tokens or max_completion_tokens, not both: providers disagree on the "
                "field name and sending both is a request they will reject"
            )
        return self


class ChatResponse(BaseModel):
    """One answer. ``model`` is what the provider reports, not what we asked for.

    It goes into ``DecisionRecord.versions.model`` (decision 20), so a replayed verdict can name
    the model that wrote the text. Token counts feed the cost metric (NFR-7).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    model: str = Field(min_length=1)
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    finish_reason: str | None = None
    latency_ms: float = Field(default=0.0, ge=0.0)


class ChatClient(Protocol):
    """What the hub and the agents depend on. One blocking call, no streaming."""

    def complete(self, request: ChatRequest) -> ChatResponse: ...


# A family is the leading letters of the model name: "Qwen/Qwen3.6-35B-A3B-FP8" and
# "Qwen3.8-27B" are both "qwen", "deepseek-chat" is "deepseek". Provider ids are free text and
# there is no registry to check them against, so this is a heuristic on the id: it catches the
# obvious mistake of pointing both roles at one provider's catalogue, and a provider that names
# ids differently would need a mapping here.
_FAMILY_PATTERN = re.compile(r"[a-z]+")


def model_family(model: str) -> str:
    """Best-effort family of a model id; raises if the id has no letters to read."""
    head = model.strip().rsplit("/", 1)[-1].lower()
    match = _FAMILY_PATTERN.match(head)
    if match is None:
        raise LlmConfigurationError(
            f"cannot read a model family from {model!r}; the guard needs an id with a name in it"
        )
    return match.group(0)


def assert_distinct_families(agent_model: str, judge_model: str) -> None:
    """Refuse a judge from the agent's own family (decision 20). Raise if they match."""
    agent_family = model_family(agent_model)
    judge_family = model_family(judge_model)
    if agent_family == judge_family:
        raise LlmConfigurationError(
            f"the judge model {judge_model!r} is from the same family as the agent model "
            f"{agent_model!r} ({agent_family}); a judge from the agent's family tends to pass its "
            "family's mistakes, so they must come from different providers (decision 20)",
            rule=LlmRule.SAME_FAMILY,
        )
