"""Tests for the System 1 loader interface (TSD-003).

The production ``LayaLoader`` is exercised against TSD-005's FakeRouter double
by replacing ``calvino.classifiers.laya._load_router``, so no test needs laya
installed, a model download or a GPU.
"""

from __future__ import annotations

import pytest

import calvino.classifiers.laya as laya_module
from calvino.api.loader import LayaLoader
from calvino.classifiers import workflow_questions


def test_loader_starts_unloaded():
    assert LayaLoader().loaded is False


def test_preload_loads_the_pinned_model_once(monkeypatch, fake_router_factory):
    router = fake_router_factory()
    monkeypatch.setattr(laya_module, "_load_router", lambda: router)
    loader = LayaLoader()

    loader.preload()

    assert loader.loaded is True
    assert router.preloaded_models == ["multilingual"]


def test_classify_delegates_to_the_client(monkeypatch, fake_router_factory):
    script = {"needs_human": {"human needed": 0.9, "can handle automatically": 0.1}}
    router = fake_router_factory(script)
    monkeypatch.setattr(laya_module, "_load_router", lambda: router)
    loader = LayaLoader()

    answers = loader.classify("mi pago no llega", workflow_questions())

    assert {answer.question_id for answer in answers} == set(workflow_questions())
    assert loader.loaded is True
    assert router.calls[0][2] == "multilingual"
    by_id = {answer.question_id: answer for answer in answers}
    assert by_id["needs_human"].probabilities["human needed"] == pytest.approx(0.9)


def test_preload_without_laya_fails_fast(monkeypatch):
    def missing_laya():
        raise RuntimeError("laya is not installed; System 1 needs it at runtime.")

    monkeypatch.setattr(laya_module, "_load_router", missing_laya)
    loader = LayaLoader()

    with pytest.raises(RuntimeError, match="laya is not installed"):
        loader.preload()

    assert loader.loaded is False
