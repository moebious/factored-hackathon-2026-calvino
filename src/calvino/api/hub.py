"""Wiring the hub into the demo API (TSD-010).

``build_demo_hub`` assembles the ``HubService`` the hub endpoints serve:
policy v1, ``BankTools`` on the dataset adapter over the bundled synthetic
fixture, the demo personas behind ``TrustedSessionIssuer``, the
``TemplateAgent`` (deterministic until T-301), the shared decision log and
the HMAC confirmation issuer from ``calvino.tools`` — one instance, so the
tools consume exactly the tokens the hub issues. The fraud context reads
the fixture's ``fraud_flagged`` entries: the harness-side risk seam, never
a model. Every input is injectable so tests build the same service on the
fake loader and the fake confirmation verifier.
"""

from __future__ import annotations

import json
from typing import Any

from calvino.api.config import ApiSettings
from calvino.api.loader import SystemOneLoader
from calvino.decision_log import DecisionLog
from calvino.hub import (
    DEMO_PERSONAS,
    HubDependencies,
    HubService,
    SupportAgent,
    TemplateAgent,
    TrustedSessionIssuer,
)
from calvino.policy import Policy
from calvino.tools import (
    BankTools,
    ConfirmationVerifier,
    DatasetAdapter,
    HmacConfirmationVerifier,
    confirmation_key_from_env,
)
from calvino.tools.session import Session
from calvino.verifier import Judge, NotRunJudge


class FixtureFraudContext:
    """The demo's ``FraudContext``: the fixture's ``fraud_flagged`` entries.

    The flags are internal bank facts the adapter never exposes through a
    tool, so the hub reads them through this seam — exactly the shape a
    production risk system would plug into.
    """

    def __init__(self, fixture: dict[str, Any]) -> None:
        self._flagged = {
            str(entry.get("customer_id"))
            for entry in fixture.get("entries", [])
            if entry.get("fraud_flagged")
        }

    def is_flagged(self, session: Session) -> bool:
        return session.customer_id in self._flagged


def build_demo_hub(
    loader: SystemOneLoader,
    settings: ApiSettings,
    policy: Policy,
    log: DecisionLog,
    confirmations: ConfirmationVerifier | None = None,
    agent: SupportAgent | None = None,
    judge: Judge | None = None,
) -> HubService:
    """Assemble the demo's ``HubService``.

    ``agent`` defaults to the deterministic ``TemplateAgent``, and only that agent gets the
    verifier's ``NotRunJudge`` when no ``judge`` is given (judged criteria are reported as not run),
    so the public demo stays keyless. A model-written reply with no judge keeps ``judge=None``: the
    cascade then fails its judged criteria closed as unverified, instead of letting unjudged model
    text through under a stand-in. The evaluation passes the LLM agent and the real judge (TSD-016).

    Without ``confirmations`` the HMAC verifier is built from
    ``CALVINO_CONFIRMATION_KEY``; a missing or short key raises
    ``ConfigurationError``, and the app then leaves the hub endpoints
    disabled (fail closed) instead of serving writes without a token path.
    """
    if confirmations is None:
        confirmations = HmacConfirmationVerifier(confirmation_key_from_env())
    fixture = json.loads(settings.bank_fixture.read_text(encoding="utf-8"))
    adapter = DatasetAdapter(fixture)
    tools = BankTools(adapter, confirmations)
    chosen_agent = agent if agent is not None else TemplateAgent()
    if judge is None and isinstance(chosen_agent, TemplateAgent):
        judge = NotRunJudge()
    deps = HubDependencies(
        loader=loader,
        policy=policy,
        tools=tools,
        issuer=TrustedSessionIssuer(DEMO_PERSONAS),
        agent=chosen_agent,
        log=log,
        judge=judge,
        fraud_context=FixtureFraudContext(fixture),
        confirmations=confirmations,
    )
    # The checkpointer follows CALVINO_DATA_DIR (sqlite on the persistent
    # mount in the deployment, memory in tests and ephemeral runs).
    return HubService(deps)
