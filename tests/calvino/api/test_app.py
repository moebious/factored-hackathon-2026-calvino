"""End-to-end tests of the demo API with the fake loader.

No network, no model, no GPU: the app is assembled with an injected FakeLoader,
settings on a temporary directory and the released policy/v1.yaml.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from calvino.api.app import PASSCODE_HEADER, RateLimiter, create_app
from calvino.api.config import ApiSettings
from calvino.classifiers import LayaAnswer, workflow_questions
from calvino.decision_log import read_records

# A calm stuck-payment message: every route threshold stays on the act side.
ACT_SCRIPT = {
    "workflow_area": {
        "stuck payment": 0.90,
        "dispute or unrecognised charge": 0.03,
        "fraud or stolen access": 0.02,
        "other banking": 0.03,
        "out of scope": 0.02,
    },
    "intent": {
        "check status": 0.90,
        "cancel transfer": 0.02,
        "retry payment": 0.02,
        "open a case": 0.02,
        "check case status": 0.02,
        "talk to a person": 0.02,
    },
    "clear_enough": {"clear": 0.95, "unclear": 0.05},
    "needs_human": {"human needed": 0.10, "can handle automatically": 0.90},
    "injection": {"risky": 0.02, "not risky": 0.98},
}

HEADERS = {PASSCODE_HEADER: "test-passcode"}


class BrokenLoader:
    """A loader whose answers are incomplete, so the decision core raises."""

    loaded = True

    def preload(self) -> None:  # pragma: no cover - trivial
        pass

    def classify(self, text: str, questions: dict[str, dict]) -> list[LayaAnswer]:
        return []


@pytest.fixture
def client(fake_loader_factory, settings, policy):
    """A started app (lifespan ran, loader preloaded) with a calm script."""
    loader = fake_loader_factory(ACT_SCRIPT)
    with TestClient(create_app(loader, settings, policy)) as started:
        yield started


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_follows_the_loader(fake_loader_factory, settings, policy):
    loader = fake_loader_factory()
    app = create_app(loader, settings, policy)

    # Before startup: the lifespan has not run, so the model is not loaded.
    assert TestClient(app).get("/ready").json() == {"ready": False}

    with TestClient(app) as started:
        assert started.get("/ready").json() == {"ready": True}
    assert loader.preload_calls == 1


def test_decide_returns_the_glass_box(client):
    response = client.post("/api/demo/decide", json={"text": "mi pago no llega"}, headers=HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "agents"
    assert body["rule_id"] == "RT-ACT"
    assert body["human_action"] == "none"
    assert body["policy_version"] == "v1"
    assert set(body["answers"]) == set(workflow_questions())
    assert body["scores"]["needs_human"] == pytest.approx(0.10)
    # act_probability carries no signal and must never appear in a payload.
    assert "act_probability" not in response.text


def test_decide_writes_the_decision_log(client, settings):
    response = client.post("/api/demo/decide", json={"text": "mi pago no llega"}, headers=HEADERS)

    records = list(read_records(settings.decisions_log))
    assert [record.decision_id for record in records] == [response.json()["decision_id"]]


def test_decide_rejects_a_missing_or_wrong_passcode(client):
    assert client.post("/api/demo/decide", json={"text": "hola"}).status_code == 403
    wrong = {PASSCODE_HEADER: "not-the-passcode"}
    assert client.post("/api/demo/decide", json={"text": "hola"}, headers=wrong).status_code == 403


def test_decide_is_disabled_without_a_configured_passcode(fake_loader_factory, policy, tmp_path):
    settings = ApiSettings(data_dir=tmp_path / "data", demo_passcode=None)
    with TestClient(create_app(fake_loader_factory(), settings, policy)) as started:
        response = started.post("/api/demo/decide", json={"text": "hola"}, headers=HEADERS)
    assert response.status_code == 503


def test_decide_validates_the_text(client):
    assert client.post("/api/demo/decide", json={"text": ""}, headers=HEADERS).status_code == 422
    long_text = "x" * 2001
    assert (
        client.post("/api/demo/decide", json={"text": long_text}, headers=HEADERS).status_code
        == 422
    )


def test_decide_rate_limits_per_client(fake_loader_factory, policy, tmp_path):
    settings = ApiSettings(
        data_dir=tmp_path / "data", demo_passcode="test-passcode", demo_rate_limit_per_minute=2
    )
    with TestClient(create_app(fake_loader_factory(ACT_SCRIPT), settings, policy)) as started:
        first = started.post("/api/demo/decide", json={"text": "uno"}, headers=HEADERS)
        second = started.post("/api/demo/decide", json={"text": "dos"}, headers=HEADERS)
        third = started.post("/api/demo/decide", json={"text": "tres"}, headers=HEADERS)

    assert (first.status_code, second.status_code) == (200, 200)
    assert third.status_code == 429
    assert int(third.headers["Retry-After"]) >= 1


def test_rate_limit_keys_on_the_forwarded_client(fake_loader_factory, policy, tmp_path):
    """Behind Vercel's rewrite the browser's IP is the first XFF entry.

    Every judge shares the rewrite's egress IP as the direct peer, so the
    limiter must key on the forwarded value or the per-client cap becomes a
    global one during judging (TSD-012).
    """
    settings = ApiSettings(
        data_dir=tmp_path / "data", demo_passcode="test-passcode", demo_rate_limit_per_minute=2
    )
    judge_a = {**HEADERS, "x-forwarded-for": "203.0.113.7, 10.0.0.1"}
    judge_b = {**HEADERS, "x-forwarded-for": "198.51.100.4"}
    with TestClient(create_app(fake_loader_factory(ACT_SCRIPT), settings, policy)) as started:
        first = started.post("/api/demo/decide", json={"text": "uno"}, headers=judge_a)
        second = started.post("/api/demo/decide", json={"text": "dos"}, headers=judge_a)
        third = started.post("/api/demo/decide", json={"text": "tres"}, headers=judge_a)
        # Judge A is at the cap; judge B on the same egress IP still has budget.
        other = started.post("/api/demo/decide", json={"text": "uno"}, headers=judge_b)

    assert (first.status_code, second.status_code, third.status_code) == (200, 200, 429)
    assert other.status_code == 200


def test_a_blank_forwarded_header_falls_back_to_the_peer(fake_loader_factory, policy, tmp_path):
    """Without a usable forwarded value the direct peer is the client."""
    settings = ApiSettings(
        data_dir=tmp_path / "data", demo_passcode="test-passcode", demo_rate_limit_per_minute=2
    )
    headers = {**HEADERS, "x-forwarded-for": ""}
    with TestClient(create_app(fake_loader_factory(ACT_SCRIPT), settings, policy)) as started:
        first = started.post("/api/demo/decide", json={"text": "uno"}, headers=headers)
        second = started.post("/api/demo/decide", json={"text": "dos"}, headers=headers)
        third = started.post("/api/demo/decide", json={"text": "tres"}, headers=headers)

    assert (first.status_code, second.status_code, third.status_code) == (200, 200, 429)


def test_a_spoofed_forwarded_header_never_bypasses_the_passcode(client):
    """The forwarded value changes only the rate limit, never authentication."""
    headers = {**HEADERS, "x-forwarded-for": "203.0.113.9"}
    headers[PASSCODE_HEADER] = "not-the-passcode"
    response = client.post("/api/demo/decide", json={"text": "hola"}, headers=headers)
    assert response.status_code == 403


def test_broken_answers_map_to_502(policy, tmp_path):
    settings = ApiSettings(data_dir=tmp_path / "data", demo_passcode="test-passcode")
    with TestClient(create_app(BrokenLoader(), settings, policy)) as started:
        response = started.post("/api/demo/decide", json={"text": "hola"}, headers=HEADERS)
    assert response.status_code == 502
    assert "decision failed" in response.json()["detail"]


def test_rate_limiter_window_slides():
    limiter = RateLimiter(per_minute=2)
    assert limiter.allow("a", now=0.0)
    assert limiter.allow("a", now=1.0)
    assert not limiter.allow("a", now=2.0)
    # A different client has its own window.
    assert limiter.allow("b", now=2.0)
    # Once the oldest hit is older than a minute, the client may proceed.
    assert limiter.allow("a", now=61.0)
    assert limiter.retry_after_seconds("missing", now=0.0) == 0
