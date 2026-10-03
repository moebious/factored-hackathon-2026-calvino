"""Tests for the live deployment smoke check (TSD-012, tests/deployment/).

Two kinds, both offline: the scenario table's coverage (it must mirror the
frontend's buttons) and the check itself against a stubbed transport —
a healthy deployment passes, a sleeping or broken one fails with evidence,
and the passcode never reaches argv or the printed output.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_deployment.py"
_spec = importlib.util.spec_from_file_location("check_deployment", SCRIPT)
assert _spec is not None and _spec.loader is not None
cd = importlib.util.module_from_spec(_spec)
# Registered before exec_module: dataclasses and typing resolve string
# annotations through sys.modules[cls.__module__], which is None otherwise.
sys.modules["check_deployment"] = cd
_spec.loader.exec_module(cd)

BASE = "https://demo.test"


# --------------------------------------------------------------------------
# Stubbed transport
# --------------------------------------------------------------------------


class StubResponse:
    def __init__(self, status_code: int = 200, payload: Any = None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = {} if payload is None else payload
        self.text = text

    def json(self) -> Any:
        return self._payload


class StubClient:
    """Routes (method, path) to a fixed response or a callable responder."""

    def __init__(self, responders: dict[tuple[str, str], Any]) -> None:
        self._responders = responders

    def _resolve(self, method: str, url: str, body: dict[str, Any] | None = None) -> StubResponse:
        path = url.split("demo.test", 1)[1]
        responder = self._responders[(method, path)]
        return responder(body) if callable(responder) else responder

    def get(self, url: str) -> StubResponse:
        return self._resolve("GET", url)

    def post(self, url: str, json: dict[str, Any]) -> StubResponse:
        return self._resolve("POST", url, json)

    def __enter__(self) -> StubClient:
        return self

    def __exit__(self, *args: object) -> None:
        return None


class _Clock:
    """A monotonic clock that advances a fixed step per reading."""

    def __init__(self, step: float) -> None:
        self._t = 0.0
        self._step = step

    def __call__(self) -> float:
        self._t += self._step
        return self._t


def _reply_body(reply: str = "Su transferencia sigue pendiente.") -> dict[str, Any]:
    return {
        "reply": reply,
        "card": {"key": "payment_status", "payload": {}},
        "trace": [{"stage": "hard_rules"}],
        "awaiting": None,
        "awaiting_ref": None,
        "needs_language": False,
        "case_ref": None,
    }


def _healthy_responders() -> dict[tuple[str, str], Any]:
    def message(body: dict[str, Any]) -> StubResponse:
        text = body["text"]
        if "reintentar" in text:
            return StubResponse(
                payload={
                    "reply": "",
                    "card": {"key": "action_confirmation", "payload": {}},
                    "trace": [{"stage": "route"}],
                    "awaiting": "approve_action",
                    "awaiting_ref": "persona-dana",
                    "needs_language": False,
                    "case_ref": None,
                }
            )
        if "hablar con una persona" in text:
            return StubResponse(
                payload={
                    "reply": "",
                    "card": {"key": "operator_queue", "payload": {}},
                    "trace": [{"stage": "route"}],
                    "awaiting": "operator_queue",
                    "awaiting_ref": "case-1",
                    "needs_language": False,
                    "case_ref": "case-1",
                }
            )
        return StubResponse(payload=_reply_body())

    def resume(body: dict[str, Any]) -> StubResponse:
        if body["decision"] is True:
            return StubResponse(
                payload={
                    "reply": "Hecho.",
                    "card": {"key": "action_result", "payload": {}},
                    "trace": [{"stage": "act"}],
                    "awaiting": None,
                    "awaiting_ref": None,
                    "needs_language": False,
                    "case_ref": None,
                }
            )
        return StubResponse(payload=_reply_body("Un agente toma tu caso."))

    return {
        ("GET", "/"): StubResponse(text="<html><title>Calvino</title></html>"),
        ("GET", "/health"): StubResponse(),
        ("GET", "/ready"): StubResponse(payload={"ready": True}),
        ("GET", "/api/hub/personas"): StubResponse(payload={"personas": list(cd.DEMO_PERSONAS)}),
        ("POST", "/api/hub/message"): message,
        ("POST", "/api/hub/resume"): resume,
    }


# --------------------------------------------------------------------------
# The scenario table mirrors the frontend's buttons
# --------------------------------------------------------------------------


def test_the_scenario_table_covers_every_button() -> None:
    ids = [scenario.id for scenario in cd.SCENARIOS]
    assert ids == ["uc-1", "uc-2", "uc-3", "uc-4", "uc-5", "uc-7", "uc-8"]
    assert {scenario.persona for scenario in cd.SCENARIOS} <= set(cd.DEMO_PERSONAS)
    kinds = {scenario.id: scenario.kind for scenario in cd.SCENARIOS}
    assert set(kinds.values()) <= {"reply", "approval", "operator"}


def test_dana_s_retry_is_the_approval_scenario() -> None:
    retry = next(scenario for scenario in cd.SCENARIOS if scenario.id == "uc-5")
    assert retry.persona == "dana"
    assert retry.kind == "approval"
    assert "reintentar" in retry.message


def test_the_operator_queue_has_its_own_scenario() -> None:
    operator = next(scenario for scenario in cd.SCENARIOS if scenario.id == "uc-4")
    assert operator.kind == "operator"


# --------------------------------------------------------------------------
# The checks against the stubbed transport
# --------------------------------------------------------------------------


def test_a_healthy_deployment_passes_every_check() -> None:
    client = StubClient(_healthy_responders())
    results = cd.run_checks(client, BASE, timeout=1.0, interval=0.0, sleep=lambda s: None)
    failures = [(r.name, r.detail) for r in results if not r.ok]
    assert failures == []
    assert len(results) == 4 + len(cd.SCENARIOS)
    assert all(r.latency_ms is not None for r in results)


def test_a_backend_that_never_wakes_fails_the_health_check() -> None:
    responders = _healthy_responders()
    responders[("GET", "/health")] = StubResponse(status_code=503)
    client = StubClient(responders)
    results = cd.run_checks(
        client, BASE, timeout=0.05, interval=0.01, sleep=lambda s: None, now=_Clock(0.02)
    )
    health = next(r for r in results if "health" in r.name)
    assert not health.ok
    assert "timeout" in health.detail and "503" in health.detail


def test_a_backend_that_never_preloads_fails_the_ready_check() -> None:
    responders = _healthy_responders()
    responders[("GET", "/ready")] = StubResponse(payload={"ready": False})
    client = StubClient(responders)
    results = cd.run_checks(
        client, BASE, timeout=0.05, interval=0.01, sleep=lambda s: None, now=_Clock(0.02)
    )
    ready = next(r for r in results if "ready" in r.name)
    assert not ready.ok


def test_a_missing_frontend_fails_the_first_check() -> None:
    responders = _healthy_responders()
    responders[("GET", "/")] = StubResponse(status_code=404, text="Not Found")
    client = StubClient(responders)
    results = cd.run_checks(client, BASE, timeout=1.0, interval=0.0, sleep=lambda s: None)
    frontend = results[0]
    assert frontend.name == "frontend served"
    assert not frontend.ok


def test_the_approval_check_fails_on_the_wrong_parked_state() -> None:
    responders = _healthy_responders()
    # A deployment whose hub never parks: every turn answers directly.
    responders[("POST", "/api/hub/message")] = lambda body: StubResponse(payload=_reply_body())
    client = StubClient(responders)
    results = cd.run_checks(client, BASE, timeout=1.0, interval=0.0, sleep=lambda s: None)
    approval = next(r for r in results if "uc-5" in r.name)
    assert not approval.ok
    assert "approve_action" in approval.detail
    operator = next(r for r in results if "uc-4" in r.name)
    assert not operator.ok
    assert "operator_queue" in operator.detail


def test_a_turn_without_a_trace_fails() -> None:
    responders = _healthy_responders()
    body = _reply_body()
    body["trace"] = []
    responders[("POST", "/api/hub/message")] = lambda payload: StubResponse(payload=body)
    client = StubClient(responders)
    results = cd.run_checks(client, BASE, timeout=1.0, interval=0.0, sleep=lambda s: None)
    reply_checks = [r for r in results if r.name.startswith("scenario uc-1")]
    assert reply_checks and not reply_checks[0].ok
    assert "trace" in reply_checks[0].detail


# --------------------------------------------------------------------------
# The CLI: the passcode stays in the environment
# --------------------------------------------------------------------------


def test_a_missing_passcode_stops_before_any_request(monkeypatch, capsys) -> None:
    monkeypatch.delenv(cd.PASSCODE_ENV, raising=False)
    code = cd.main(["--url", BASE])
    captured = capsys.readouterr()
    assert code == 2
    assert cd.PASSCODE_ENV in captured.err


def test_the_passcode_never_reaches_the_output(monkeypatch, capsys) -> None:
    monkeypatch.setenv(cd.PASSCODE_ENV, "s3cret-passcode-value")
    code = cd.main(
        ["--url", BASE],
        client_factory=lambda headers, timeout: StubClient(_healthy_responders()),
    )
    captured = capsys.readouterr()
    total = 4 + len(cd.SCENARIOS)
    assert code == 0
    assert f"{total}/{total} checks passed" in captured.out
    assert "s3cret-passcode-value" not in captured.out
    assert "[measured]" in captured.out


def test_a_failing_check_exits_one(monkeypatch, capsys) -> None:
    monkeypatch.setenv(cd.PASSCODE_ENV, "s3cret-passcode-value")
    responders = _healthy_responders()
    responders[("GET", "/health")] = StubResponse(status_code=503)

    def factory(headers: dict[str, str], timeout: float) -> StubClient:
        return StubClient(responders)

    code = cd.main(["--url", BASE, "--timeout", "0"], client_factory=factory)
    captured = capsys.readouterr()
    assert code == 1
    assert "FAIL" in captured.out
    assert "s3cret-passcode-value" not in captured.out
