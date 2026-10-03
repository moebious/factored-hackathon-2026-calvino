"""Demo API (TSD-003, TSD-010): the HTTP surface of the deployed skeleton.

Serves ``GET /health``, ``GET /ready``, ``POST /api/demo/decide`` and the
hub endpoints (``/api/hub/message``, ``/api/hub/resume``,
``/api/hub/personas``) on the Hugging Face Space (FastAPI, Docker, port
7860). Model loading sits behind ``SystemOneLoader`` (fake in tests,
``LayaLoader`` in the container), the demo hub is wired by ``build_demo_hub``
over the synthetic bank fixture, and all deployment configuration comes
from environment variables (``config``).
"""

from calvino.api.app import DemoDecideRequest, HubMessageRequest, HubResumeRequest, create_app
from calvino.api.config import ApiSettings, settings_from_env
from calvino.api.decide import DemoAnswer, DemoDecision, run_demo_decision, scores_from_answers
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
