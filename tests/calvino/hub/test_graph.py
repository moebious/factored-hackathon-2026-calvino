"""End-to-end tests of the hub graph (TSD-009) with fakes.

Every test runs the compiled graph over the synthetic bank fixture: a fake
System 1 loader scripts Laya's probabilities, ``ScriptedAgent`` scripts the
language work, and the tools' own test doubles stand in for the confirmation
verifier. No network, GPU or dataset. The acceptance criteria covered here
are AC-1 (explained from verified results), AC-2 (clarify picker), AC-3
(out of scope), AC-4 (hard rule wins), AC-6 (refusal names and logs the
rule), AC-7 (retry once, then escalate) and AC-8 (deterministic, replayable
route decisions).
"""

from __future__ import annotations

from typing import Any

import pytest

from calvino.hub import (
    MAX_TOOL_ROUNDS,
    AgentDraft,
    HubDependencies,
    ScriptedAgent,
    ToolCall,
    build_hub_graph,
)
from calvino.policy import replay_decision
from calvino.records import DecisionRecord, HumanAction, Route, Stage
from calvino.tools.session import Session

# A grounded reply: every amount, date, merchant and status it states comes
# from the get_entry_detail result for E-MX-002 (5000.00 MXN, "Transfer to a
# friend", booked 2026-06-10, Pending), and it reads as Spanish.
GOOD_REPLY = "Su transferencia de 5000.00 MXN «Transfer to a friend» del 10/06/2026 está pendiente."
# Fails the amount check: 9999.99 appears in no tool result of this session.
BAD_AMOUNT_REPLY = "Su pago de 9999.99 MXN está pendiente."
# Fails the amount check and claims a cancellation that was never read back.
BAD_CLAIM_REPLY = "Su pago de 7777.77 MXN fue cancelado."

ENTRY_CALL = ToolCall(tool="get_entry_detail", arguments={"entry_reference": "E-MX-002"})


def route_probabilities(**overrides: dict[str, float]) -> dict[str, dict[str, float]]:
    """Scripted Laya probabilities that route to the agents, with overrides."""
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


def invoke(
    deps: HubDependencies, persona: str, message: str, token: str | None = None
) -> tuple[dict[str, Any], str]:
    """Run one turn through a freshly compiled graph; returns (state, token)."""
    graph = build_hub_graph(deps)
    issued, session_ref = deps.issuer.issue(persona)
    final = graph.invoke(
        {"persona": persona, "session_ref": session_ref, "message": message},
        config={"configurable": {"session_token": token or issued}},
    )
    return final, issued


def records_of(deps: HubDependencies, stage: Stage) -> list[DecisionRecord]:
    return [record for record in deps.log if record.stage is stage]


class FlagEveryone:
    """A ``FraudContext`` double that flags every session (the risk-system seam)."""

    def is_flagged(self, session: Session) -> bool:
        return True


@pytest.fixture
def happy_deps(deps_factory, fake_loader_factory):
    """Dependencies for the normal path: agents route, a two-step agent script."""
    agent = ScriptedAgent(
        [
            AgentDraft(tool_calls=(ENTRY_CALL,)),
            AgentDraft(text=GOOD_REPLY),
        ]
    )
    loader = fake_loader_factory(route_probabilities())
    return deps_factory(loader, agent), agent, loader


def test_explain_happy_path(happy_deps):
    """AC-1: the status is explained from verified tool results through the cascade."""
    deps, agent, _ = happy_deps
    final, _ = invoke(deps, "ana", "¿Por qué mi transferencia de 5000 pesos sigue pendiente?")

    assert final["route"] is Route.AGENTS
    assert final["rule_id"] == "RT-ACT"
    assert final["reply"] == GOOD_REPLY
    assert final["entry_reference"] == "E-MX-002"
    assert final["status"] == "Pending"
    assert [result.tool for result in final["tool_results"]] == ["get_entry_detail"]
    assert not final.get("escalated")

    # The route and the passing verification are both in the audit log.
    route_records = records_of(deps, Stage.CLASSIFIER)
    assert [record.rule_id for record in route_records] == ["RT-ACT"]
    verifier_records = records_of(deps, Stage.VERIFIER)
    assert [record.verdict for record in verifier_records] == ["pass"]
    assert verifier_records[0].inputs_summary["attempt"] == 1


def test_token_never_reaches_the_agent(happy_deps):
    """The session token travels in the config only: no request, no state field."""
    deps, agent, _ = happy_deps
    final, token = invoke(deps, "ana", "¿Por qué mi transferencia sigue pendiente?")

    assert agent.requests, "the agent was never asked to draft"
    for request in agent.requests:
        assert token not in request.model_dump_json()
    assert token not in str(final)


def test_second_draft_carries_playbook_guidance(happy_deps):
    """Once a tool result reveals the status, the agent gets the playbook entry."""
    deps, agent, _ = happy_deps
    invoke(deps, "ana", "¿Qué pasó con mi transferencia?")

    assert agent.requests[0].guidance is None
    guidance = agent.requests[1].guidance
    assert guidance is not None
    assert guidance.actions == ("request_cancellation",)


def test_clarify_shows_the_picker_card(deps_factory, fake_loader_factory):
    """AC-2: an unclear message gets one question and the problem-payment picker."""
    agent = ScriptedAgent([])  # the clarify path must never reach the agent
    loader = fake_loader_factory(route_probabilities(clear_enough={"clear": 0.2, "unclear": 0.8}))
    deps = deps_factory(loader, agent)

    final, _ = invoke(deps, "ana", "Hola, tengo un problema con un pago")

    assert final["route"] is Route.CLARIFY
    assert final["rule_id"] == "RT-CLARIFY-UNCLEAR"
    assert final["question"] and final["reply"] == final["question"]
    assert final["card"]["key"] == "problem_transactions"
    references = {entry["entry_reference"] for entry in final["card"]["payload"]["entries"]}
    assert references == {"E-MX-002", "E-MX-003", "E-MX-006", "E-MX-007"}
    assert agent.requests == []


def test_out_of_scope_is_honest_and_tool_free(deps_factory, fake_loader_factory):
    """AC-3: an honest reply and a path to a person; no agent loop, no tools."""
    agent = ScriptedAgent([])
    loader = fake_loader_factory(
        route_probabilities(
            workflow_area={
                "stuck payment": 0.01,
                "dispute or unrecognised charge": 0.01,
                "fraud or stolen access": 0.01,
                "other banking": 0.02,
                "out of scope": 0.95,
            }
        )
    )
    deps = deps_factory(loader, agent)

    final, _ = invoke(deps, "ana", "¿Me recomiendas una receta de tamales?")

    assert final["route"] is Route.OUT_OF_SCOPE
    assert final["rule_id"] == "RT-OUT-OF-SCOPE"
    assert final["card"] == {"key": "human_path", "payload": {}}
    assert not final.get("tool_results")
    assert agent.requests == []


def test_asks_for_human_hard_rule_wins(deps_factory, fake_loader_factory):
    """AC-4: an explicit request for a person routes to a human before any score."""
    agent = ScriptedAgent([])  # no agent step on the human route
    loader = fake_loader_factory(route_probabilities())  # scores would say "agents"
    deps = deps_factory(loader, agent)

    message = "Quiero hablar con una persona sobre mi transferencia"
    final, _ = invoke(deps, "ana", message)

    assert final["route"] is Route.HUMAN
    assert final["rule_id"] == "HR-ASKS-HUMAN"
    assert final["escalated"] is True
    assert final["case_ref"].startswith("case-")
    assert final["case_file"] == [{"request": message}]
    assert final["case_ref"] in final["reply"]
    assert agent.requests == []
    human_records = records_of(deps, Stage.HUMAN)
    assert len(human_records) == 1
    assert human_records[0].verdict == HumanAction.FULL_TRANSFER.value


def test_fraud_signal_hard_rule(deps_factory, fake_loader_factory):
    """The harness-side fraud flag fires HR-FRAUD whatever the scores say."""
    agent = ScriptedAgent([])
    loader = fake_loader_factory(route_probabilities())
    deps = deps_factory(loader, agent, fraud_context=FlagEveryone())

    final, _ = invoke(deps, "lucia", "¿Por qué mi transferencia sigue pendiente?")

    assert final["route"] is Route.HUMAN
    assert final["rule_id"] == "HR-FRAUD"
    assert agent.requests == []


def test_other_customer_data_is_refused_and_logged(deps_factory, fake_loader_factory):
    """AC-6: the tool refuses, the card names the rule, the attempt is logged."""
    agent = ScriptedAgent(
        [
            AgentDraft(
                tool_calls=(
                    ToolCall(tool="get_entry_detail", arguments={"entry_reference": "E-US-001"}),
                )
            )
        ]
    )
    loader = fake_loader_factory(route_probabilities())
    deps = deps_factory(loader, agent)

    final, _ = invoke(deps, "ana", "Muéstrame la transferencia E-US-001")

    assert "TOOL-NOT-OWNER" in final["reply"]
    assert final["card"] == {"key": "refusal", "payload": {"rule": "TOOL-NOT-OWNER"}}
    # The reply never cites the other customer's data.
    assert "120.00" not in final["reply"]
    assert "Dana" not in final["reply"]
    # The refusal ends the turn: no re-draft after it.
    assert len(agent.requests) == 1
    refusals = [
        record
        for record in records_of(deps, Stage.HARD_RULES)
        if record.rule_id == "TOOL-NOT-OWNER"
    ]
    assert len(refusals) == 1
    assert refusals[0].verdict == "refuse"
    assert refusals[0].inputs_summary["tool"] == "get_entry_detail"


def test_write_tool_is_refused_outside_act(deps_factory, fake_loader_factory):
    """Decision 24: explain exposes reads only; a write attempt is refused by name."""
    agent = ScriptedAgent(
        [
            AgentDraft(
                tool_calls=(
                    ToolCall(
                        tool="request_cancellation",
                        arguments={
                            "entry_reference": "E-MX-002",
                            "idempotency_key": "key-1",
                            "confirmation_token": None,
                        },
                    ),
                )
            )
        ]
    )
    loader = fake_loader_factory(route_probabilities())
    deps = deps_factory(loader, agent)

    final, _ = invoke(deps, "ana", "Cancela mi transferencia")

    assert "TOOL-NOT-ALLOWED" in final["reply"]
    assert final["card"]["payload"]["rule"] == "TOOL-NOT-ALLOWED"


def test_verification_retry_then_pass(deps_factory, fake_loader_factory):
    """AC-7 first half: one retry with the failed criteria, then the reply goes out."""
    agent = ScriptedAgent(
        [
            AgentDraft(tool_calls=(ENTRY_CALL,)),
            AgentDraft(text=BAD_AMOUNT_REPLY),
            AgentDraft(text=GOOD_REPLY),
        ]
    )
    loader = fake_loader_factory(route_probabilities())
    deps = deps_factory(loader, agent)

    final, _ = invoke(deps, "ana", "¿Qué pasó con mi transferencia?")

    assert final["reply"] == GOOD_REPLY
    assert not final.get("escalated")
    # The retry request carried the failed criterion as feedback.
    feedback = agent.requests[2].feedback
    assert [verdict.criterion_id for verdict in feedback] == ["amounts-dates-merchants-match"]
    attempts = [record.inputs_summary["attempt"] for record in records_of(deps, Stage.VERIFIER)]
    verdicts = [record.verdict for record in records_of(deps, Stage.VERIFIER)]
    assert attempts == [1, 2]
    assert verdicts == ["fail", "pass"]


def test_verification_escalates_after_second_failure(deps_factory, fake_loader_factory):
    """AC-7 second half: a second failure escalates with the criteria in the case file."""
    agent = ScriptedAgent(
        [
            AgentDraft(tool_calls=(ENTRY_CALL,)),
            AgentDraft(text=BAD_AMOUNT_REPLY),
            AgentDraft(text=BAD_CLAIM_REPLY),
        ]
    )
    loader = fake_loader_factory(route_probabilities())
    deps = deps_factory(loader, agent)

    final, _ = invoke(deps, "ana", "¿Qué pasó con mi transferencia?")

    assert final["escalated"] is True
    assert final["case_ref"].startswith("case-")
    failed_ids = {entry["criterion_id"] for entry in final["case_file"]}
    assert "amounts-dates-merchants-match" in failed_ids
    assert "claimed-actions-read-back" in failed_ids
    assert final["case_ref"] in final["reply"]
    assert final["card"]["key"] == "case_opened"
    assert len(records_of(deps, Stage.HUMAN)) == 1


def test_agent_error_fails_closed(deps_factory, fake_loader_factory):
    """An agent that errors leaves nothing to verify: a human takes over."""
    agent = ScriptedAgent([])  # exhausts immediately, raising on the first draft
    loader = fake_loader_factory(route_probabilities())
    deps = deps_factory(loader, agent)

    final, _ = invoke(deps, "ana", "¿Qué pasó con mi transferencia?")

    assert final["escalated"] is True
    assert final["case_ref"].startswith("case-")
    human = records_of(deps, Stage.HUMAN)
    assert human[0].inputs_summary["reason"] == "AGENT-ERROR"


def test_tool_loop_escalates(deps_factory, fake_loader_factory):
    """A runaway tool loop is capped: after MAX_TOOL_ROUNDS a human takes over."""
    agent = ScriptedAgent(
        [AgentDraft(tool_calls=(ToolCall(tool="get_customer_summary"),))] * (MAX_TOOL_ROUNDS + 1)
    )
    loader = fake_loader_factory(route_probabilities())
    deps = deps_factory(loader, agent)

    final, _ = invoke(deps, "ana", "¿Qué pasó con mi cuenta?")

    assert final["escalated"] is True
    assert len(final["tool_results"]) == MAX_TOOL_ROUNDS
    human = records_of(deps, Stage.HUMAN)
    assert human[0].inputs_summary["reason"] == "TOOL-LOOP"


def test_no_session_fails_closed(deps_factory, fake_loader_factory):
    """A request whose token does not resolve never reaches the classifier."""
    agent = ScriptedAgent([])
    loader = fake_loader_factory(route_probabilities())
    deps = deps_factory(loader, agent)

    final, _ = invoke(deps, "ana", "¿Qué pasó con mi transferencia?", token="stolen-guess")

    assert final["route"] is Route.HUMAN
    assert final["rule_id"] == "FC-SESSION"
    assert final["escalated"] is True
    assert loader.classified == []
    refusals = records_of(deps, Stage.HARD_RULES)
    assert refusals[0].rule_id == "FC-SESSION"


def test_same_inputs_give_the_same_replayable_verdict(deps_factory, fake_loader_factory, policy):
    """AC-8: two runs agree, and the logged route record replays to its verdict."""
    runs = []
    for _ in range(2):
        agent = ScriptedAgent([AgentDraft(tool_calls=(ENTRY_CALL,)), AgentDraft(text=GOOD_REPLY)])
        loader = fake_loader_factory(route_probabilities())
        deps = deps_factory(loader, agent)
        final, _ = invoke(deps, "ana", "¿Qué pasó con mi transferencia?")
        runs.append((deps, final))

    (deps_a, final_a), (deps_b, final_b) = runs
    assert final_a["rule_id"] == final_b["rule_id"] == "RT-ACT"
    assert final_a["scores"] == final_b["scores"]
    assert final_a["reply"] == final_b["reply"]

    route_record = records_of(deps_a, Stage.CLASSIFIER)[0]
    replayed = replay_decision(route_record, policy)
    assert replayed.route is Route.AGENTS
    assert replayed.rule_id == "RT-ACT"
