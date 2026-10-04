"""Fixtures for the demo API tests (TSD-003).

FakeLoader is the ``SystemOneLoader`` double, one level above TSD-005's
FakeRouter: it returns validated ``LayaAnswer`` records instead of a raw laya
payload. It lives in tests on purpose: production code can never import it.
"""

from __future__ import annotations

import pytest

from calvino.api.config import ApiSettings
from calvino.classifiers import LayaAnswer
from calvino.policy import load_policy


class FakeLoader:
    """A ``SystemOneLoader`` double with scripted probabilities per question id.

    Unscripted questions get uniform probabilities over the real workflow
    question options, so a test that scripts one question still gets a
    complete answer set. ``loaded`` mirrors LayaClient's lazy preload.
    """

    def __init__(self, probabilities_by_qid: dict[str, dict[str, float]] | None = None) -> None:
        self.probabilities_by_qid = probabilities_by_qid or {}
        self.loaded = False
        self.preload_calls = 0
        self.classified: list[tuple[str, dict[str, dict]]] = []

    def preload(self) -> None:
        self.preload_calls += 1
        self.loaded = True

    def classify(self, text: str, questions: dict[str, dict]) -> list[LayaAnswer]:
        self.classified.append((text, dict(questions)))
        if not self.loaded:
            self.loaded = True
        answers = []
        for question_id, question in questions.items():
            keys = list(question["criteria"].keys())
            probs = self.probabilities_by_qid.get(question_id)
            if probs is None:
                probs = {key: 1.0 / len(keys) for key in keys}
            total = sum(probs.values())
            probs = {key: round(value / total, 4) for key, value in probs.items()}
            answers.append(
                LayaAnswer(
                    question_id=question_id,
                    chosen_option=max(probs, key=probs.get),
                    probabilities=probs,
                    confidence=max(probs.values()),
                )
            )
        return answers


@pytest.fixture
def fake_loader_factory():
    """The FakeLoader class, so tests can build one with scripted probabilities."""
    return FakeLoader


@pytest.fixture(scope="session")
def policy():
    """The released policy (v2), loaded exactly as the API loads it."""
    return load_policy()


@pytest.fixture
def settings(tmp_path):
    """API settings on a temporary data dir."""
    return ApiSettings(data_dir=tmp_path / "data")
