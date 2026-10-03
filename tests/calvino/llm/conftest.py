"""Test doubles for the LLM client (TSD-008).

``FakeChatClient`` lives in tests on purpose, like ``FakeRouter``: production code must never be
able to import a fake model.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from calvino.llm.contracts import (
    ChatRequest,
    ChatResponse,
    Message,
    MessageRole,
    Role,
)


class FakeChatClient:
    """Stands in for any ``ChatClient`` with scripted replies and no network.

    Replies are keyed by the request's ``purpose``, so one fake can serve the agent and the judge
    in the same test. Every request is recorded, which is how tests assert what was sent without
    a transport.
    """

    def __init__(
        self,
        replies: dict[str, str] | None = None,
        *,
        default_reply: str = "",
        model: str = "fake-model",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> None:
        self._replies = dict(replies or {})
        self._default = default_reply
        self._model = model
        self._prompt_tokens = prompt_tokens
        self._completion_tokens = completion_tokens
        self.requests: list[ChatRequest] = []

    def complete(self, request: ChatRequest) -> ChatResponse:
        self.requests.append(request)
        return ChatResponse(
            text=self._replies.get(request.purpose or "", self._default),
            model=self._model,
            prompt_tokens=self._prompt_tokens,
            completion_tokens=self._completion_tokens,
            finish_reason="stop",
            latency_ms=1.0,
        )


def one_message_request(
    text: str, *, role: Role = Role.AGENT, purpose: str | None = None
) -> ChatRequest:
    """The smallest request the interface accepts: one user turn."""
    return ChatRequest(
        role=role,
        messages=(Message(role=MessageRole.USER, content=text),),
        purpose=purpose,
    )


@pytest.fixture
def fake_chat_client_factory() -> Callable[..., FakeChatClient]:
    """The FakeChatClient class, so tests can build one with scripted replies."""
    return FakeChatClient


@pytest.fixture
def chat_request() -> Callable[..., ChatRequest]:
    """A builder for the smallest valid request."""
    return one_message_request
