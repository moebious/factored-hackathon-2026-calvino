"""Shared fixtures for calvino tests.

FakeRouter is the test double for ``laya.Router`` (TSD-005). It lives in tests
on purpose: production code must never be able to import a fake model.
"""

from __future__ import annotations

import pytest


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
