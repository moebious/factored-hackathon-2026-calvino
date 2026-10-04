"""Demo API (TSD-003, TSD-010): the HTTP surface of the deployed skeleton.

Serves ``GET /health``, ``GET /ready``, ``POST /api/demo/decide`` and the
hub endpoints (``/api/hub/message``, ``/api/hub/resume``,
``/api/hub/personas``) on the Hugging Face Space (FastAPI, Docker, port
7860). Model loading sits behind ``SystemOneLoader`` (fake in tests,
``LayaLoader`` in the container), the demo hub is wired by ``build_demo_hub``
over the synthetic bank fixture, and all deployment configuration comes
from environment variables (``config``).

Every name below is resolved on first use (PEP 562) rather than imported
here. The eager version was a cycle: ``calvino.hub.graph`` imports
``calvino.api.decide`` for ``scores_from_answers``, importing that submodule
ran this package, which imported ``app``, which imported ``calvino.api.hub``,
which imported ``calvino.hub`` while ``calvino.hub.__init__`` was still
executing. It only showed up as ``ImportError: cannot import name
'DEMO_PERSONAS'`` when ``calvino.hub`` was imported first, so the full test
suite passed and ``pytest tests/calvino/hub`` failed. Deferring the imports
breaks the cycle: ``calvino.api.decide`` needs only ``loader`` and the core
packages, none of which reach back here.

The public names are unchanged, so ``from calvino.api import create_app``
still works exactly as before.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - imports for type checkers and readers only
    from calvino.api.app import DemoDecideRequest, HubMessageRequest, HubResumeRequest, create_app
    from calvino.api.config import ApiSettings, settings_from_env
    from calvino.api.decide import (
        DemoAnswer,
        DemoDecision,
        run_demo_decision,
        scores_from_answers,
    )
    from calvino.api.hub import FixtureFraudContext, build_demo_hub
    from calvino.api.loader import LayaLoader, SystemOneLoader

__all__ = [
    "ApiSettings",
    "DemoAnswer",
    "DemoDecideRequest",
    "DemoDecision",
    "FixtureFraudContext",
    "HubMessageRequest",
    "HubResumeRequest",
    "LayaLoader",
    "SystemOneLoader",
    "build_demo_hub",
    "create_app",
    "run_demo_decision",
    "scores_from_answers",
    "settings_from_env",
]

# Public name -> the submodule that defines it. A test asserts this covers __all__ exactly.
_SUBMODULES: dict[str, str] = {
    "ApiSettings": "calvino.api.config",
    "DemoAnswer": "calvino.api.decide",
    "DemoDecideRequest": "calvino.api.app",
    "DemoDecision": "calvino.api.decide",
    "FixtureFraudContext": "calvino.api.hub",
    "HubMessageRequest": "calvino.api.app",
    "HubResumeRequest": "calvino.api.app",
    "LayaLoader": "calvino.api.loader",
    "SystemOneLoader": "calvino.api.loader",
    "build_demo_hub": "calvino.api.hub",
    "create_app": "calvino.api.app",
    "run_demo_decision": "calvino.api.decide",
    "scores_from_answers": "calvino.api.decide",
    "settings_from_env": "calvino.api.config",
}


def __getattr__(name: str) -> Any:
    """Resolve one public name by importing only the submodule that defines it."""
    module_name = _SUBMODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    # Cache it, so the second access does not go through here again.
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return list(__all__)
