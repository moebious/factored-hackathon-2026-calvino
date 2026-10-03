"""Shared fixtures for calvino tests.

FakeRouter is the test double for ``laya.Router`` (TSD-005) and FakeChatClient
the one for ``ChatClient`` (TSD-009). They live in tests on purpose:
production code must never be able to import a fake model.
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


class FakeRouter:
    """Stands in for ``laya.Router`` with scripted probabilities per question id.

    ``predict`` returns the real laya 0.3.x payload shape, including
    ``action.act_probability``, so tests prove the client strips it. Questions
    without a scripted answer come back with uniform probabilities.
    """

    def __init__(self, probabilities_by_qid: dict[str, dict[str, float]] | None = None):
        self.probabilities_by_qid = probabilities_by_qid or {}
        self.preloaded_models: list[str] | None = None
        self.calls: list[tuple[str, dict, str | None]] = []

    def preload(self, names=None) -> None:
        self.preloaded_models = list(names or [])

    def predict(self, state, questions, model=None) -> dict:
        self.calls.append((state, dict(questions), model))
        answers = {}
        for qid, question in questions.items():
            keys = list(question["criteria"].keys())
            probs = self.probabilities_by_qid.get(qid)
            if probs is None:
                probs = {key: 1.0 / len(keys) for key in keys}
            total = sum(probs.values())
            probs = {k: round(v / total, 4) for k, v in probs.items()}
            chosen = max(probs, key=probs.get)
            answers[qid] = {
                "type": "choice",
                "choice": chosen,
                "probabilities": probs,
                "confidence": 0.5,  # normalized entropy; the client ignores it
                "answer_confidence": max(probs.values()),
                "action": {"act_probability": 0.42},
            }
        return {"answers": answers, "usage": {"total_tokens": 0}}


@pytest.fixture
def fake_router_factory():
    """The FakeRouter class, so tests can build one with scripted probabilities."""
    return FakeRouter


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
