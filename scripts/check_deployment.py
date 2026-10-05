#!/usr/bin/env python3
"""Live smoke check of the deployed demo (TSD-012).

Proves the deployment task's "done when" on the public origin: the
frontend is served, the backend wakes (``/health``) and preloads
(``/ready``), and every scenario button's turn works through the hub
endpoints — including the parked approval and the operator queue flows.
One line per check with its latency ``[measured]``; exit 0 only when
every check passes.

The endpoints are open (decision 38); the smoke check needs no credentials.
The HTTP client is ``httpx``, a dev dependency (FastAPI's TestClient),
so ``uv run`` has it; the script stays out of the runtime image and out
of CI — it needs the live URL.

Usage:
    uv run python scripts/check_deployment.py \
        --url https://calvino.rubrica.dev
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

# The demo personas, mirrored from calvino.hub.sessions (DEMO_PERSONAS).
# Deliberately hardcoded: importing the package here would drag in the
# whole hub and its API/langgraph import chain (which cycles back through
# calvino.hub when calvino.api is imported first) for four stable names.
DEMO_PERSONAS = ("ana", "camilo", "lucia", "dana")

# The frontend's metadata title (frontend/app/layout.tsx): the cheapest
# marker that the UI itself is served, not only the API rewrite.
FRONTEND_MARKER = "Calvino"


@dataclass(frozen=True)
class Scenario:
    """One scenario button's turn: who sends what, and what must come back.

    ``kind`` is what the check asserts structurally (never text equality —
    live Laya scores differ from the seeded test probabilities). Every
    kind requires a non-empty trace; only ``reply`` requires a card or
    reply text, because a parked turn legitimately carries neither (the
    operator queue parks with an empty reply and no card):

    - ``reply``: a 200 with a card or a non-empty reply, and a non-empty trace
    - ``approval``: the turn parks with ``approve_action`` and an
      ``action_confirmation`` card; the resume with ``decision: true``
      returns an ``action_result`` card
    - ``operator``: the turn parks with ``operator_queue``; the resume with
      a decision string returns a 200
    """

    id: str
    persona: str
    message: str
    kind: str


# Mirrors frontend/app/scenarios.ts (TSD-012): the same personas and
# messages the scenario buttons send. Keep the two files in step; the
# coverage test in tests/deployment/ checks this table's shape. The
# messages are tuned to laya 0.3.27's measured scores under policy v3
# (decision 30): each one lands on the route its use case demonstrates.
SCENARIOS: tuple[Scenario, ...] = (
    Scenario("uc-1", "ana", "Mi pago E-MX-002 sigue pendiente, ¿qué pasa?", "reply"),
    Scenario("uc-2", "ana", "Tengo un problema", "reply"),
    Scenario("uc-3", "camilo", "¿Puedes ayudarme con mi tarea de matemáticas?", "reply"),
    Scenario("uc-4", "ana", "Quiero hablar con una persona sobre mi transferencia", "operator"),
    Scenario("uc-5", "dana", "Reintentar transferencia E-US-001", "approval"),
    Scenario("uc-7", "ana", "Muéstrame la transferencia E-US-001", "reply"),
    Scenario("uc-8", "ana", "¿Cómo va el caso que abrí por mi pago?", "reply"),
)

# The operator's resume decision: any short string closes the queue turn.
OPERATOR_DECISION = "assigned to operator"


class Client(Protocol):
    """The slice of ``httpx.Client`` the checks use (stubbed in tests)."""

    def get(self, url: str) -> httpx.Response: ...

    def post(self, url: str, json: dict[str, Any]) -> httpx.Response: ...


@dataclass(frozen=True)
class CheckResult:
    """One check's outcome: name, verdict, evidence, and latency if timed."""

    name: str
    ok: bool
    detail: str
    latency_ms: float | None = None


def _poll(
    client: Client,
    url: str,
    predicate: Callable[[httpx.Response], tuple[bool, str]],
    timeout: float,
    interval: float,
    sleep: Callable[[float], None],
    now: Callable[[], float],
) -> tuple[bool, float, str]:
    """GET ``url`` until the predicate passes or the timeout expires."""
    start = now()
    deadline = start + timeout
    detail = "no response yet"
    while True:
        try:
            ok, detail = predicate(client.get(url))
        except httpx.TransportError as error:
            ok = False
            detail = f"unreachable ({error.__class__.__name__})"
        if ok:
            return True, (now() - start) * 1000.0, detail
        if now() >= deadline:
            return False, (now() - start) * 1000.0, f"timeout after {timeout:g} s: {detail}"
        sleep(interval)


def _hub_post(
    client: Client, url: str, payload: dict[str, Any]
) -> tuple[dict[str, Any] | None, str]:
    """One hub POST: (body, "") on success, or (None, why it failed).

    Never retried: a retry could double-fire a write, and the check stays
    read-honest (TSD-012).
    """
    try:
        response = client.post(url, json=payload)
    except httpx.TransportError as error:
        return None, f"unreachable ({error.__class__.__name__})"
    if response.status_code != 200:
        return None, f"expected 200, got {response.status_code}"
    body = response.json()
    if not isinstance(body, dict):
        return None, "expected a JSON object"
    return body, ""


def _turn_evidence(body: dict[str, Any]) -> str:
    """Why a reply-kind turn is not a valid outcome ("" when it is).

    Reply kind only: a parked turn legitimately carries neither a card
    nor reply text (the operator queue parks with both empty; the
    approval park's card is checked by its own branch), so demanding
    one here would fail a healthy deployment.
    """
    if body.get("card") is None and not str(body.get("reply") or ""):
        return "neither a card nor a non-empty reply"
    return ""


def _check_scenario(client: Client, base_url: str, scenario: Scenario) -> CheckResult:
    """Run one scenario button's turn against the live hub endpoints."""
    name = f"scenario {scenario.id} ({scenario.persona})"
    start = time.monotonic()
    ok, detail = _scenario_evidence(client, base_url, scenario)
    return CheckResult(name, ok, detail, _ms_since(start))


def _scenario_evidence(client: Client, base_url: str, scenario: Scenario) -> tuple[bool, str]:
    """The scenario's verdict and evidence, per its kind."""
    message_url = f"{base_url}/api/hub/message"
    resume_url = f"{base_url}/api/hub/resume"
    body, problem = _hub_post(
        client, message_url, {"persona": scenario.persona, "text": scenario.message}
    )
    if body is None:
        return False, problem
    if not body.get("trace"):
        return False, "the trace is empty (the harness logged nothing)"

    if scenario.kind == "reply":
        if body.get("awaiting") is not None:
            return False, f"unexpected parked turn: {body['awaiting']!r}"
        evidence = _turn_evidence(body)
        if evidence:
            return False, evidence
        return True, "a card or reply with a trace"

    if scenario.kind == "approval":
        if body.get("awaiting") != "approve_action":
            return False, f"expected approve_action, got {body.get('awaiting')!r}"
        card = body.get("card") or {}
        if card.get("key") != "action_confirmation":
            return False, f"expected the action_confirmation card, got {card.get('key')!r}"
        ref = body.get("awaiting_ref")
        if not ref:
            return False, "the parked turn carries no awaiting_ref"
        resumed, problem = _hub_post(client, resume_url, {"ref": ref, "decision": True})
        if resumed is None:
            return False, f"resume failed: {problem}"
        card = resumed.get("card") or {}
        if card.get("key") != "action_result":
            return False, f"expected the action_result card, got {card.get('key')!r}"
        return True, "parked, confirmed, executed"

    # The operator queue: park, then close with a decision string.
    if body.get("awaiting") != "operator_queue":
        return False, f"expected operator_queue, got {body.get('awaiting')!r}"
    ref = body.get("awaiting_ref")
    if not ref:
        return False, "the parked turn carries no awaiting_ref"
    resumed, problem = _hub_post(client, resume_url, {"ref": ref, "decision": OPERATOR_DECISION})
    if resumed is None:
        return False, f"resume failed: {problem}"
    return True, "queued and resumed"


def _ms_since(start: float) -> float:
    return (time.monotonic() - start) * 1000.0


def run_checks(
    client: Client,
    base_url: str,
    timeout: float = 300.0,
    interval: float = 5.0,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.monotonic,
) -> list[CheckResult]:
    """Every check, in order; all run even when one fails (no retries)."""
    results: list[CheckResult] = []

    start = now()
    try:
        response = client.get(f"{base_url}/")
        served = response.status_code == 200 and FRONTEND_MARKER in response.text
        detail = (
            "the frontend is served"
            if served
            else f"expected 200 containing {FRONTEND_MARKER!r}, got {response.status_code}"
        )
    except httpx.TransportError as error:
        served = False
        detail = f"unreachable ({error.__class__.__name__})"
    results.append(CheckResult("frontend served", served, detail, (now() - start) * 1000.0))

    ok, elapsed, detail = _poll(
        client,
        f"{base_url}/health",
        lambda r: (r.status_code == 200, f"health returned {r.status_code}"),
        timeout,
        interval,
        sleep,
        now,
    )
    results.append(CheckResult("backend awake (/health)", ok, detail, elapsed))

    ok, elapsed, detail = _poll(
        client,
        f"{base_url}/ready",
        lambda r: (
            r.status_code == 200 and bool(r.json().get("ready")),
            f"ready returned {r.status_code}",
        ),
        timeout,
        interval,
        sleep,
        now,
    )
    results.append(CheckResult("model preloaded (/ready)", ok, detail, elapsed))

    start = now()
    personas_ok = False
    detail = ""
    try:
        response = client.get(f"{base_url}/api/hub/personas")
    except httpx.TransportError as error:
        detail = f"unreachable ({error.__class__.__name__})"
    else:
        if response.status_code != 200:
            detail = f"expected 200, got {response.status_code}"
        else:
            got = set(response.json().get("personas", []))
            personas_ok = got == set(DEMO_PERSONAS)
            detail = (
                "the demo personas are offered"
                if personas_ok
                else f"expected {sorted(DEMO_PERSONAS)}, got {sorted(got)}"
            )
    results.append(CheckResult("personas endpoint", personas_ok, detail, _ms_since(start)))

    for scenario in SCENARIOS:
        results.append(_check_scenario(client, base_url, scenario))

    return results


def main(argv: list[str] | None = None, client_factory: Any = httpx.Client) -> int:
    """Run every check against ``--url``; exit 0 only when all pass.

    ``client_factory`` is injectable so the tests run main() end to end
    without a network.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", required=True, help="the public origin (the Vercel domain)")
    parser.add_argument("--timeout", type=float, default=300.0, help="cold-start budget, seconds")
    parser.add_argument("--interval", type=float, default=5.0, help="poll interval, seconds")
    args = parser.parse_args(argv)

    base_url = str(args.url).rstrip("/")
    with client_factory(timeout=60.0) as client:
        results = run_checks(client, base_url, timeout=args.timeout, interval=args.interval)

    for result in results:
        mark = " ok " if result.ok else "FAIL"
        latency = f"{result.latency_ms:8.0f} ms [measured]" if result.latency_ms is not None else ""
        print(f"[{mark}] {result.name:<34} {latency}  {result.detail}")
    passed = sum(1 for result in results if result.ok)
    print(f"{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
