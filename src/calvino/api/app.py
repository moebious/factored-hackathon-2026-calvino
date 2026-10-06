"""The demo API application (TSD-003, TSD-010).

``create_app`` assembles the FastAPI app: ``GET /health`` (process up),
``GET /ready`` (true once Laya is loaded), ``POST /api/demo/decide`` (one
System 1 decision on a short text) and the hub endpoints (TSD-010):
``POST /api/hub/message``, ``POST /api/hub/resume`` and
``GET /api/hub/personas``, serving the ``HubService`` over the synthetic
bank fixture. Every demo endpoint is open, with the same per-client rate
limit shared across them. The hub is wired at startup and stays disabled
when its confirmation key is missing (fail closed), so writes never lose
their token path. The loader preloads during startup, never on the first
request. Every collaborator is injectable so tests run without laya.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

import anyio.to_thread
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from calvino.api.config import ApiSettings, settings_from_env
from calvino.api.decide import DemoDecision, run_demo_decision
from calvino.api.hub import build_demo_hub
from calvino.api.loader import SystemOneLoader
from calvino.decision_log import DecisionLog
from calvino.hub import DEMO_PERSONAS, HubReply, HubService, OperatorQueueItem
from calvino.policy import Policy, load_policy
from calvino.tools import ConfigurationError

# "A short text" (TSD-003): the demo classifies one customer message, and the
# bound keeps latency and abuse costs sane on a free-tier Space.
MAX_DEMO_TEXT_CHARS = 2000


class DemoDecideRequest(BaseModel):
    """The demo request: one short customer message."""

    text: str = Field(min_length=1, max_length=MAX_DEMO_TEXT_CHARS)


class HubMessageRequest(BaseModel):
    """One customer turn: a demo persona or sandbox guest and their message (TSD-010, TSD-036)."""

    text: str = Field(min_length=1, max_length=MAX_DEMO_TEXT_CHARS)
    persona: str | None = Field(default=None, max_length=64)
    guest_id: str | None = Field(default=None, max_length=64)


class HubResumeRequest(BaseModel):
    """Continue a parked turn with the human's decision.

    ``decision`` is the customer's approval (true) or denial (false) for
    ``approve_action``, and the operator's decision string for
    ``operator_queue``. The string is bounded like every demo input: it
    reaches the decision log and the case file.
    """

    ref: str = Field(min_length=1)
    decision: bool | Annotated[str, Field(min_length=1, max_length=200)]


class RateLimiter:
    """A fixed-window per-client rate limit, in process.

    Deliberately simple: the demo is one container, so a sliding window in
    memory is enough; a distributed limiter is a production concern (DESIGN
    4.0.2). ``now`` is injected so tests do not have to sleep.
    """

    def __init__(self, per_minute: int) -> None:
        self.per_minute = per_minute
        self._hits: dict[str, deque[float]] = {}

    def allow(self, key: str, now: float) -> bool:
        """Record a hit and say whether it is within the limit."""
        window_start = now - 60.0
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= window_start:
            hits.popleft()
        if len(hits) >= self.per_minute:
            return False
        hits.append(now)
        return True

    def retry_after_seconds(self, key: str, now: float) -> int:
        """Seconds until the client's oldest hit leaves the window."""
        hits = self._hits.get(key)
        if not hits:
            return 0
        return max(1, int(hits[0] + 60.0 - now) + 1)


def client_key(request: Request) -> str:
    """The client identity the rate limit keys on.

    Behind Vercel's rewrite every judge reaches the Space from the same
    egress IP, so keying on the direct peer would turn the per-client cap
    into a global one during judging. Vercel forwards the browser's IP as
    the first ``X-Forwarded-For`` entry; a client hitting the Space URL
    directly can spoof the header, which weakens the rate limit and
    nothing else (the demo is open; NFR-8 trade-off, TSD-012).
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    first = forwarded.split(",")[0].strip()
    if first:
        return first
    return request.client.host if request.client is not None else "unknown"


def create_app(
    loader: SystemOneLoader,
    settings: ApiSettings | None = None,
    policy: Policy | None = None,
    hub: HubService | None = None,
) -> FastAPI:
    """Assemble the demo API. Settings come from the environment by default.

    ``hub`` is injectable for tests; when omitted, the startup wires the
    demo hub itself (and leaves it disabled when the confirmation key is
    missing, fail closed).
    """
    settings = settings if settings is not None else settings_from_env()
    policy = policy if policy is not None else load_policy()
    log = DecisionLog(settings.decisions_log)
    limiter = RateLimiter(settings.demo_rate_limit_per_minute)

    def guard(request: Request) -> None:
        """The per-client rate limit every open demo endpoint shares."""
        client = client_key(request)
        now = time.monotonic()
        if not limiter.allow(client, now):
            raise HTTPException(
                status_code=429,
                detail="rate limit exceeded",
                headers={"Retry-After": str(limiter.retry_after_seconds(client, now))},
            )

    def hub_or_503(request: Request) -> HubService:
        """The wired hub, or a 503: without it no hub turn can be served."""
        service = request.app.state.hub
        if service is None:
            raise HTTPException(status_code=503, detail="the hub is not configured")
        return service

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Preload at startup in a worker thread: laya's load is a blocking
        # 20-25 s call on CPU and must never happen on the first request.
        # Without laya installed this raises here, failing the boot fast.
        await anyio.to_thread.run_sync(loader.preload)
        if app.state.hub is None:
            try:
                app.state.hub = await anyio.to_thread.run_sync(
                    lambda: build_demo_hub(loader, settings, policy, log)
                )
            except (ConfigurationError, OSError, ValueError):
                # A missing confirmation key, fixture or a broken file
                # disables the hub endpoints; decide keeps working.
                app.state.hub = None
        yield

    app = FastAPI(title="Calvino demo API", version="0.1.0", lifespan=lifespan)
    app.state.hub = hub

    @app.get("/health")
    async def health() -> dict[str, str]:
        """The process is up (does not imply the model is loaded)."""
        return {"status": "ok"}

    @app.get("/ready")
    async def ready() -> dict[str, bool]:
        """True once Laya is loaded; the frontend warm-up screen polls this."""
        return {"ready": loader.loaded}

    @app.post("/api/demo/decide", response_model=DemoDecision)
    async def demo_decide(payload: DemoDecideRequest, request: Request) -> DemoDecision:
        """Run one System 1 decision on a short text."""
        guard(request)
        try:
            # classify and the policy call are blocking; keep the loop free.
            return await anyio.to_thread.run_sync(
                lambda: run_demo_decision(payload.text, loader, policy, log)
            )
        except ValueError as error:
            # Incomplete or drifted laya answers: the upstream side is broken,
            # not the caller's request.
            raise HTTPException(status_code=502, detail=f"decision failed: {error}") from error

    @app.get("/api/hub/personas")
    async def hub_personas(request: Request) -> dict[str, list[str]]:
        """The demo persona names the app's selector offers (TSD-010)."""
        guard(request)
        return {"personas": list(DEMO_PERSONAS)}

    @app.get("/api/hub/cases", response_model=list[OperatorQueueItem])
    async def hub_cases(request: Request) -> list[OperatorQueueItem]:
        """List active cases in the operator queue or pending human approval (TSD-023)."""
        guard(request)
        service = hub_or_503(request)
        return await anyio.to_thread.run_sync(service.list_cases)

    @app.post("/api/hub/message", response_model=HubReply)
    async def hub_message(payload: HubMessageRequest, request: Request) -> HubReply:
        """Run one customer turn through the hub."""
        guard(request)
        service = hub_or_503(request)
        try:
            # The turn classifies, calls tools and verifies: all blocking.
            return await anyio.to_thread.run_sync(
                lambda: service.handle_message(
                    persona=payload.persona,
                    text=payload.text,
                    guest_id=payload.guest_id,
                )
            )
        except KeyError as error:
            # An unknown persona fails closed at the issuer.
            raise HTTPException(status_code=404, detail=f"unknown persona: {error}") from error

    @app.post("/api/hub/resume", response_model=HubReply)
    async def hub_resume(payload: HubResumeRequest, request: Request) -> HubReply:
        """Continue a parked turn with the human's decision."""
        guard(request)
        service = hub_or_503(request)
        try:
            return await anyio.to_thread.run_sync(
                lambda: service.resume(payload.ref, payload.decision)
            )
        except ValueError as error:
            # Gate block violation or invalid decision raises ValueError (403 Forbidden).
            raise HTTPException(status_code=403, detail=str(error)) from error
        except KeyError as error:
            # An unknown ref fails closed at the service.
            raise HTTPException(status_code=404, detail=f"no parked turn: {error}") from error

    return app
