"""The System 1 loader interface for the demo API (TSD-003).

Model loading sits behind this small interface so the API and every test depend
only on ``SystemOneLoader``: tests inject a fake, and the real ``laya`` package
is loaded only in the container, where ``LayaLoader.preload`` runs at startup.
Never on the first request: the first call pays a 20-25 s checkpoint load on
CPU (HANDOFF pitfalls).
"""

from __future__ import annotations

from typing import Protocol

from calvino.classifiers import CheckpointRef, LayaAnswer, LayaClient


class SystemOneLoader(Protocol):
    """What the API needs from System 1."""

    @property
    def loaded(self) -> bool:
        """True once the model is in memory; backs ``GET /ready``."""
        ...

    def preload(self) -> None:
        """Load the model once. Called at startup; must fail fast when missing."""
        ...

    def classify(self, text: str, questions: dict[str, dict]) -> list[LayaAnswer]:
        """Answer typed questions about one customer message."""
        ...


class LayaLoader:
    """The production loader: wraps the merged ``LayaClient`` (TSD-005).

    Constructing it is safe without ``laya`` installed (the client imports the
    package lazily); ``preload`` then fails fast with installation instructions.
    Only the container installs laya (see the Dockerfile), so unit tests never
    need a model download.
    """

    def __init__(
        self, model: str = "multilingual", checkpoint: CheckpointRef | None = None
    ) -> None:
        self._client = LayaClient(model, checkpoint=checkpoint)
        self._loaded = False

    @property
    def loaded(self) -> bool:
        return self._loaded

    def preload(self) -> None:
        self._client.preload()
        self._loaded = True

    def classify(self, text: str, questions: dict[str, dict]) -> list[LayaAnswer]:
        answers = self._client.classify(text, questions)
        # LayaClient preloads lazily inside classify; mirror that for /ready.
        self._loaded = True
        return answers
