"""Demo API (TSD-003): the HTTP surface of the deployed skeleton.

Serves ``GET /health``, ``GET /ready`` and ``POST /api/demo/decide`` on the
Hugging Face Space (FastAPI, Docker, port 7860). Model loading sits behind
``SystemOneLoader`` (fake in tests, ``LayaLoader`` in the container), and all
deployment configuration comes from environment variables (``config``).
"""

from calvino.api.config import ApiSettings, settings_from_env
from calvino.api.decide import DemoAnswer, DemoDecision, run_demo_decision, scores_from_answers
from calvino.api.loader import LayaLoader, SystemOneLoader

__all__ = [
    "ApiSettings",
    "DemoAnswer",
    "DemoDecision",
    "LayaLoader",
    "SystemOneLoader",
    "run_demo_decision",
    "scores_from_answers",
    "settings_from_env",
]
