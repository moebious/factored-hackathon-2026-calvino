"""Shared fixtures for the hub tests (TSD-009).

``FakeLoader`` is the ``SystemOneLoader`` double, mirroring the one in
``tests/calvino/api/conftest.py``: it returns validated ``LayaAnswer`` records
with scripted probabilities per question id, and uniform probabilities for
unscripted questions. ``deps_factory`` builds ``HubDependencies`` on the
synthetic bank fixture with the test doubles the tools and verifier ship, so
graph tests run with no network, GPU or dataset.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from calvino.classifiers import LayaAnswer
from calvino.decision_log import DecisionLog
from calvino.hub import DEMO_PERSONAS, HubDependencies, SupportAgent, TrustedSessionIssuer
from calvino.hub.graph import FraudContext
from calvino.policy import Policy, load_policy
from calvino.tools import BankTools, DatasetAdapter, FakeConfirmationVerifier

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "bank" / "synthetic_bank.json"
NOW = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)

# The demo personas: fixture customers, never a customer number typed in
# chat. One source (calvino.hub.sessions), shared with the demo API.
PERSONAS = DEMO_PERSONAS


class FakeLoader:
    """A ``SystemOneLoader`` double with scripted probabilities per question id.

    Unscripted questions get uniform probabilities over the real workflow
    question options, so a test that scripts one question still gets a
    complete answer set.
    """

    def __init__(self, probabilities_by_qid: dict[str, dict[str, float]] | None = None) -> None:
        self.probabilities_by_qid = probabilities_by_qid or {}
        self.loaded = False
        self.classified: list[tuple[str, dict[str, dict]]] = []

    def preload(self) -> None:
        self.loaded = True

    def classify(self, text: str, questions: dict[str, dict]) -> list[LayaAnswer]:
        self.classified.append((text, dict(questions)))
        self.loaded = True
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
def fake_loader_factory():
    """The FakeLoader class, so tests can build one with scripted probabilities."""
    return FakeLoader


@pytest.fixture(scope="session")
def policy() -> Policy:
    """The released policy (v2), loaded exactly as the hub loads it."""
    return load_policy()


@pytest.fixture
def deps_factory(tmp_path, policy):
    """Build ``HubDependencies`` on the bank fixture with the given doubles."""

    def make(
        loader: object,
        agent: SupportAgent,
        fraud_context: FraudContext | None = None,
        with_confirmations: bool = True,
    ) -> HubDependencies:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        adapter = DatasetAdapter(fixture, clock=lambda: NOW)
        # One verifier for both sides: the tools consume the tokens the hub
        # issues through the same instance, exactly like the shared HMAC key.
        confirmations = FakeConfirmationVerifier()
        tools = BankTools(adapter, confirmations, clock=lambda: NOW)
        return HubDependencies(
            loader=loader,  # type: ignore[arg-type]
            policy=policy,
            tools=tools,
            issuer=TrustedSessionIssuer(PERSONAS),
            agent=agent,
            log=DecisionLog(tmp_path / "decisions.jsonl"),
            fraud_context=fraud_context,
            confirmations=confirmations if with_confirmations else None,
        )

    return make


# Seeded-scenario scoreboard (decision 23): the scenario runner appends one
# line per green scenario, and the terminal summary prints the board on
# every pytest run, so a scenario that passes is visibly never lost again.
SCENARIO_SCOREBOARD: list[str] = []


@pytest.fixture(scope="session")
def scenario_scoreboard() -> list[str]:
    """The session's scenario scoreboard lines (see tests/scenarios/)."""
    return SCENARIO_SCOREBOARD


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print the seeded-scenario scoreboard at the end of every run."""
    if SCENARIO_SCOREBOARD:
        terminalreporter.write_sep("=", "scenario scoreboard (decision 23)")
        for line in SCENARIO_SCOREBOARD:
            terminalreporter.write_line(line)
