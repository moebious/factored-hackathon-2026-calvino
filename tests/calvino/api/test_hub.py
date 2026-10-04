"""Tests of the hub HTTP endpoints (TSD-010).

The app is assembled with an injected ``HubService`` built by the real
``build_demo_hub`` over the bundled fixture, a scripted System One loader
and a fake confirmation verifier, so the endpoints are tested end to end
without laya or the HMAC key. Covered: the open endpoints, the disabled
hub (no confirmation key), the explain turn with its card and trace, the
parked approval with the confirmation card and its resume, the operator
queue flow, the fail-closed unknown persona and ref, and the shared rate
limit.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from calvino.api.app import create_app
from calvino.api.config import ApiSettings, settings_from_env
from calvino.api.hub import build_demo_hub
from calvino.classifiers import LayaAnswer
from calvino.decision_log import DecisionLog
from calvino.policy import load_policy
from calvino.tools import FakeConfirmationVerifier

DANA_EXPLAIN = "Su transferencia de 120.00 USD «Tuition» del 2026-06-15 está rechazada."


def route_probabilities(**overrides: dict[str, float]) -> dict[str, dict[str, float]]:
    """Scripted Laya probabilities that route to the agents, with overrides.

    A local copy of the hub tests' helper: test modules are not importable
    packages, and the API tests script the same System One seam.
    """
    base = {
        "workflow_area": {
            "stuck payment": 0.97,
            "dispute or unrecognised charge": 0.01,
            "fraud or stolen access": 0.01,
            "other banking": 0.005,
            "out of scope": 0.005,
        },
        "intent": {
            "check status": 0.9,
            "cancel transfer": 0.02,
            "retry payment": 0.02,
            "open a case": 0.02,
            "check case status": 0.02,
            "talk to a person": 0.02,
        },
        "clear_enough": {"clear": 0.95, "unclear": 0.05},
        "needs_human": {"human needed": 0.05, "can handle automatically": 0.95},
        "injection": {"risky": 0.01, "not risky": 0.99},
    }
    base.update(overrides)
    return base


class ScriptedLoader:
    """A ``SystemOneLoader`` double with scripted probabilities per question id.

    Unscripted questions get uniform probabilities over the real workflow
    question options, so a test that scripts one question still gets a
    complete answer set (a local copy of the hub tests' FakeLoader).
    """

    def __init__(self, probabilities_by_qid: dict[str, dict[str, float]]) -> None:
        self.probabilities_by_qid = probabilities_by_qid
        self.loaded = False

    def preload(self) -> None:
        self.loaded = True

    def classify(self, text: str, questions: dict[str, dict]) -> list[LayaAnswer]:
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
def make_hub_client(tmp_path, monkeypatch):
    """A factory of TestClients whose app serves a real wired hub."""
    monkeypatch.delenv("CALVINO_CONFIRMATION_KEY", raising=False)

    def build(**probability_overrides: dict[str, float]) -> TestClient:
        loader = ScriptedLoader(route_probabilities(**probability_overrides))
        settings = ApiSettings(data_dir=tmp_path)
        log = DecisionLog(settings.decisions_log)
        hub = build_demo_hub(
            loader, settings, load_policy(), log, confirmations=FakeConfirmationVerifier()
        )
        return TestClient(create_app(loader, settings, policy=load_policy(), hub=hub))

    return build


def test_personas_is_open(make_hub_client):
    """The personas endpoint needs no credentials: first request works."""
    with make_hub_client() as client:
        response = client.get("/api/hub/personas")
    assert response.status_code == 200
    assert response.json() == {"personas": ["ana", "camilo", "lucia", "dana"]}


def test_message_explain_returns_reply_card_and_trace(make_hub_client):
    """Dana's explain turn: the grounded reply, the FR-7 card, the trace."""
    with make_hub_client() as client:
        response = client.post(
            "/api/hub/message",
            json={"persona": "dana", "text": "¿Por qué mi transferencia E-US-001 sigue pendiente?"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == DANA_EXPLAIN
    assert body["escalated"] is False
    assert body["route"] == "agents"
    assert body["awaiting"] is None
    assert body["card"]["key"] == "payment_status"
    assert body["card"]["payload"]["entry_reference"] == "E-US-001"
    assert body["card"]["payload"]["status"] == "Declined"
    assert body["trace"], "the glass box reads the trace"
    assert body["trace"][0]["stage"] == "classifier"
    assert body["trace"][0]["rule_id"] == "RT-ACT"
    assert [step["stage"] for step in body["trace"]] == ["classifier", "verifier"]


def test_approval_parks_with_confirmation_card_and_resumes(make_hub_client):
    """An ask verdict parks with the confirmation card; approving executes."""
    # clear_enough 0.6 routes to the agents but is below the Gate's 0.70.
    with make_hub_client(clear_enough={"clear": 0.6, "unclear": 0.4}) as client:
        parked = client.post(
            "/api/hub/message",
            json={"persona": "dana", "text": "¿Pueden reintentar mi transferencia E-US-001?"},
        ).json()
        assert parked["awaiting"] == "approve_action"
        assert parked["awaiting_ref"] == "persona-dana"
        assert parked["reply"] == ""
        assert parked["card"] == {
            "key": "action_confirmation",
            "payload": {
                "action": "retry_payment",
                "entry_reference": "E-US-001",
                "amount": "120.00",
                "currency": "USD",
            },
        }

        final = client.post(
            "/api/hub/resume",
            json={"ref": parked["awaiting_ref"], "decision": True},
        )
    assert final.status_code == 200
    body = final.json()
    assert body["reply"] == (
        "He reintentado su transferencia de 120.00 USD «Tuition» del 2026-06-15; "
        "el nuevo pago está rechazado."
    )
    assert body["escalated"] is False
    assert body["route"] == "agents"
    assert body["card"] == {
        "key": "action_result",
        "payload": {
            "action": "retry_payment",
            "entry_reference": "E-US-001",
            "status": "Declined",
        },
    }


def test_ineligible_action_is_refused_with_a_card(make_hub_client):
    """Cancelling a declined payment is refused by the Gate, naming the rule."""
    with make_hub_client() as client:
        response = client.post(
            "/api/hub/message",
            json={"persona": "dana", "text": "Cancela mi transferencia E-US-001"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["card"] == {"key": "refusal", "payload": {"rule": "GATE-INELIGIBLE"}}
    assert body["awaiting"] is None
    assert "GATE-INELIGIBLE" in body["reply"]


def test_operator_queue_parks_and_resumes_over_http(make_hub_client):
    """The human route parks on the queue; the operator's resume closes it."""
    with make_hub_client() as client:
        parked = client.post(
            "/api/hub/message",
            json={"persona": "ana", "text": "Quiero hablar con una persona"},
        ).json()
        assert parked["awaiting"] == "operator_queue"
        case_ref = parked["case_ref"]
        assert case_ref is not None

        final = client.post(
            "/api/hub/resume",
            json={"ref": case_ref, "decision": "assigned to operator 7"},
        )
    assert final.status_code == 200
    assert case_ref in final.json()["reply"]


def test_unknown_persona_fails_closed(make_hub_client):
    """A persona outside the demo set is a 404, not a guessed session."""
    with make_hub_client() as client:
        response = client.post(
            "/api/hub/message",
            json={"persona": "nobody", "text": "hola"},
        )
    assert response.status_code == 404


def test_resume_unknown_ref_fails_closed(make_hub_client):
    """An unknown ref is a 404: the service never guesses a thread."""
    with make_hub_client() as client:
        response = client.post(
            "/api/hub/resume",
            json={"ref": "case-nope", "decision": "whatever"},
        )
    assert response.status_code == 404


def test_overlong_text_is_rejected(make_hub_client):
    """The demo text limit covers the hub endpoints too."""
    with make_hub_client() as client:
        response = client.post(
            "/api/hub/message",
            json={"persona": "dana", "text": "x" * 2001},
        )
    assert response.status_code == 422


def test_overlong_operator_decision_is_rejected(make_hub_client):
    """The operator's decision string is bounded too: it reaches the log."""
    with make_hub_client() as client:
        response = client.post(
            "/api/hub/resume",
            json={"ref": "case-1", "decision": "x" * 201},
        )
    assert response.status_code == 422


def test_rate_limit_covers_the_hub_endpoints(tmp_path, monkeypatch):
    """The per-client limit is shared: the third call in a minute is a 429."""
    monkeypatch.delenv("CALVINO_CONFIRMATION_KEY", raising=False)
    settings = ApiSettings(data_dir=tmp_path, demo_rate_limit_per_minute=2)
    app = create_app(ScriptedLoader(route_probabilities()), settings)
    with TestClient(app) as client:
        first = client.get("/api/hub/personas")
        second = client.get("/api/hub/personas")
        third = client.get("/api/hub/personas")
    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert int(third.headers["Retry-After"]) > 0


def test_hub_endpoints_stay_off_without_a_confirmation_key(tmp_path, monkeypatch):
    """No confirmation key means the hub is disabled, fail closed."""
    monkeypatch.delenv("CALVINO_CONFIRMATION_KEY", raising=False)
    settings = settings_from_env(
        env={
            "CALVINO_DATA_DIR": str(tmp_path),
        }
    )
    loader = ScriptedLoader(route_probabilities())
    app = create_app(loader, settings)  # no injected hub; startup tries to wire one
    with TestClient(app) as client:
        response = client.post(
            "/api/hub/message",
            json={"persona": "dana", "text": "hola"},
        )
    assert response.status_code == 503


def test_only_the_template_agent_gets_the_not_run_judge(tmp_path, monkeypatch):
    """A model-written reply with no judge must fail closed, not pass under a stand-in."""
    from calvino.hub import ScriptedAgent, TemplateAgent
    from calvino.verifier import NotRunJudge

    monkeypatch.delenv("CALVINO_CONFIRMATION_KEY", raising=False)
    settings = ApiSettings(data_dir=tmp_path, demo_passcode="s3cret")

    def judge_of(**kwargs):
        hub = build_demo_hub(
            ScriptedLoader(route_probabilities()),
            settings,
            load_policy(),
            DecisionLog(settings.decisions_log),
            confirmations=FakeConfirmationVerifier(),
            **kwargs,
        )
        return hub._deps.judge, hub._deps.agent

    judge, agent = judge_of()
    assert isinstance(judge, NotRunJudge) and isinstance(agent, TemplateAgent)
    judge, _ = judge_of(agent=ScriptedAgent([]))
    assert judge is None  # fails closed as unverified
    explicit = NotRunJudge()
    judge, _ = judge_of(agent=ScriptedAgent([]), judge=explicit)
    assert judge is explicit
