"""End-to-end tests of the hub graph (TSD-009) with fakes.

Every test runs the compiled graph over the synthetic bank fixture: a fake
System 1 loader scripts Laya's probabilities, ``ScriptedAgent`` scripts the
language work, and the tools' own test doubles stand in for the confirmation
verifier. No network, GPU or dataset. The acceptance criteria covered here
are AC-1 (explained from verified results), AC-2 (clarify picker), AC-3
(out of scope), AC-4 (hard rule wins), AC-6 (refusal names and logs the
rule), AC-7 (retry once, then escalate) and AC-8 (deterministic, replayable
route decisions), plus the act stage: allow with a confirmation token and a
verified read-back, ask with ``interrupt()`` and resume, block naming the
rule, and the fail-closed paths around them; and the human stages:
investigate with the complete case file and the bank case, the operator
queue interrupt, and follow-up turns on a thread with an open case; plus
the FR-7 cards, filled only from verified tool results.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from calvino.hub import (
    MAX_TOOL_ROUNDS,
    AgentDraft,
    HubDependencies,
    HubStage,
    ScriptedAgent,
    ToolCall,
    build_hub_graph,
)
from calvino.hub.graph import verified_card
from calvino.policy import replay_decision
from calvino.records import DecisionRecord, HumanAction, Route, Stage
from calvino.tools import BankTools, CleanedTableAdapter
from calvino.tools.session import Session
from calvino.verifier.evidence import ToolResult

CLEANED_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "cleaned_bank"

# A grounded reply: every amount, date, merchant and status it states comes
# from the get_entry_detail result for E-MX-002 (5000.00 MXN, "Transfer to a
# friend", booked 2026-06-10, Pending), and it reads as Spanish.
GOOD_REPLY = "Su transferencia de 5000.00 MXN «Transfer to a friend» del 10/06/2026 está pendiente."
# Fails the amount check: 9999.99 appears in no tool result of this session.
BAD_AMOUNT_REPLY = "Su pago de 9999.99 MXN está pendiente."
# Fails the amount check and claims a cancellation that was never read back.
BAD_CLAIM_REPLY = "Su pago de 7777.77 MXN fue cancelado."
# Grounded after a cancellation of E-MX-002: the amount and merchant come
# from the Gate's read, and the claim is covered by the cancel read-back.
ACT_REPLY = "He cancelado su transferencia de 5000.00 MXN «Transfer to a friend»."
# Grounded after a retry of E-US-001 (120.00 USD, Declined): the new payment
# the retry result carries is Pending, so "pendiente" matches a record.
RETRY_REPLY = "He reintentado su transferencia de 120.00 USD; el nuevo pago está pendiente."

ENTRY_CALL = ToolCall(tool="get_entry_detail", arguments={"entry_reference": "E-MX-002"})
CANCEL_CALL = ToolCall(tool="request_cancellation", arguments={"entry_reference": "E-MX-002"})
RETRY_CALL = ToolCall(tool="retry_payment", arguments={"entry_reference": "E-US-001"})


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
    # FR-7: the verified entry detail fills the payment status card.
    assert final["card"]["key"] == "payment_status"
    assert final["card"]["payload"]["entry_reference"] == "E-MX-002"
    assert final["card"]["payload"]["currency"] == "MXN"
    assert final["card"]["payload"]["status"] == "Pending"
    assert final["card"]["payload"]["booking_date"] == "2026-06-10"

    # The route and the passing verification are both in the audit log.
    route_records = records_of(deps, Stage.CLASSIFIER)
    assert [record.rule_id for record in route_records] == ["RT-ACT"]
    verifier_records = records_of(deps, Stage.VERIFIER)
    assert [record.verdict for record in verifier_records] == ["pass"]
    assert verifier_records[0].inputs_summary["attempt"] == 1


def test_verified_card_fills_only_from_tool_payloads():
    """FR-7: the card the verify pass emits comes from the verified results:
    payment status from the entry detail, case status on a follow-up, and
    nothing on the act stage (its node emits the action result itself)."""
    detail = ToolResult(
        tool="get_entry_detail",
        payload={
            "entry_reference": "E-MX-002",
            "amount": "5000.00",
            "currency": "MXN",
            "status": "Pending",
            "booking_date": "2026-06-10",
            "remittance_information": "Transfer to a friend",
        },
    )
    assert verified_card({"stage": HubStage.EXPLAIN, "tool_results": [detail]}) == {
        "key": "payment_status",
        "payload": {
            "entry_reference": "E-MX-002",
            "amount": "5000.00",
            "currency": "MXN",
            "status": "Pending",
            "booking_date": "2026-06-10",
            "remittance_information": "Transfer to a friend",
        },
    }

    investigation = ToolResult(
        tool="get_investigation_status",
        payload={"case_id": "CASE-1", "status": "InReview", "next_step": "We will call you"},
    )
    follow_state = {
        "stage": HubStage.FOLLOW_UP,
        "case_ref": "CASE-1",
        "tool_results": [investigation],
    }
    assert verified_card(follow_state) == {
        "key": "case_status",
        "payload": {"case_ref": "CASE-1", "status": "InReview", "next_step": "We will call you"},
    }

    # The act stage emits its own action_result card; verify adds nothing.
    assert verified_card({"stage": HubStage.ACT, "tool_results": [detail]}) is None
    # A turn without the matching verified result gets no card.
    assert verified_card({"stage": HubStage.EXPLAIN, "tool_results": []}) is None


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
    assert references == {"E-MX-002", "E-MX-003", "E-MX-006", "E-MX-007", "E-MX-008"}
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
    """AC-4: an explicit request for a person routes to a human before any
    score, parks the turn on the operator queue, and ends with the case open."""
    agent = ScriptedAgent([])  # no agent step on the human route
    loader = fake_loader_factory(route_probabilities())  # scores would say "agents"
    deps = deps_factory(loader, agent)

    message = "Quiero hablar con una persona sobre mi transferencia"
    graph = build_hub_graph(deps, checkpointer=InMemorySaver())
    issued, session_ref = deps.issuer.issue("ana")
    config = {"configurable": {"thread_id": "t-human", "session_token": issued}}
    paused = graph.invoke(
        {"persona": "ana", "session_ref": session_ref, "message": message}, config=config
    )

    # The turn parks on the operator queue with the complete case file; no
    # payment was focused, so the case ref is the generated fallback.
    payload = paused["__interrupt__"][0].value
    assert payload["type"] == "operator_queue"
    assert payload["reason"] == "HR-ASKS-HUMAN"
    assert paused["case_ref"].startswith("case-")
    assert paused["case_file"] == [
        {"request": message},
        {"open_question": "routed to a human by HR-ASKS-HUMAN"},
    ]

    final = graph.invoke(Command(resume="assigned to operator 7"), config=config)

    assert final["route"] is Route.HUMAN
    assert final["rule_id"] == "HR-ASKS-HUMAN"
    assert final["escalated"] is True
    assert final["case_ref"] == paused["case_ref"]
    assert final["case_ref"] in final["reply"]
    assert final["card"] == {
        "key": "case_opened",
        "payload": {"case_ref": final["case_ref"]},
    }
    assert agent.requests == []
    human_records = records_of(deps, Stage.HUMAN)
    assert len(human_records) == 1
    assert human_records[0].verdict == HumanAction.FULL_TRANSFER.value
    assert "assigned to operator 7" in str(human_records[0].inputs_summary)


def test_fraud_signal_hard_rule(deps_factory, fake_loader_factory):
    """The harness-side fraud flag fires HR-FRAUD whatever the scores say."""
    agent = ScriptedAgent([])
    loader = fake_loader_factory(route_probabilities())
    deps = deps_factory(loader, agent, fraud_context=FlagEveryone())

    graph = build_hub_graph(deps, checkpointer=InMemorySaver())
    issued, session_ref = deps.issuer.issue("lucia")
    config = {"configurable": {"thread_id": "t-fraud", "session_token": issued}}
    paused = graph.invoke(
        {
            "persona": "lucia",
            "session_ref": session_ref,
            "message": "¿Por qué mi transferencia sigue pendiente?",
        },
        config=config,
    )

    assert paused["__interrupt__"][0].value["reason"] == "HR-FRAUD"
    final = graph.invoke(Command(resume="reviewed by the risk team"), config=config)
    assert final["route"] is Route.HUMAN
    assert final["rule_id"] == "HR-FRAUD"
    assert final["escalated"] is True
    assert agent.requests == []


@pytest.mark.parametrize("missing_field", ["amount", "currency"])
def test_gate_routes_to_human_when_source_confirmation_fact_is_missing(
    deps_factory, fake_loader_factory, missing_field: str
):
    """A nullable read remains visible, but the Gate never coerces missing facts."""
    agent = ScriptedAgent([AgentDraft(tool_calls=(CANCEL_CALL,))])
    deps = deps_factory(fake_loader_factory(route_probabilities()), agent)
    adapter = deps.tools._adapter
    original = adapter._records["E-MX-002"]
    adapter._records["E-MX-002"] = original.model_copy(
        update={"entry": original.entry.model_copy(update={missing_field: None})}
    )

    final, _ = invoke(deps, "ana", "Cancela la transferencia E-MX-002")

    assert final["escalate_reason"] == "FC-INCOMPLETE-SOURCE"
    assert final["rule_id"] == "FC-INCOMPLETE-SOURCE"
    assert final["escalated"] is True
    assert final["tool_results"][0].payload[missing_field] is None
    assert adapter.action_log == []
    gate_records = records_of(deps, Stage.GATE)
    assert [(record.rule_id, record.verdict) for record in gate_records] == [
        ("FC-INCOMPLETE-SOURCE", "block")
    ]
    assert deps.confirmations is not None
    assert deps.confirmations._granted == set()


def test_cleaned_adapter_missing_facts_fail_closed_at_the_gate(
    deps_factory, fake_loader_factory, tmp_path
):
    """The cleaned source reaches the Hub as nulls and never as invented zero amounts."""
    agent = ScriptedAgent(
        [
            AgentDraft(
                tool_calls=(
                    ToolCall(
                        tool="request_cancellation",
                        arguments={"entry_reference": "E-CO-002"},
                    ),
                )
            )
        ]
    )
    deps = deps_factory(fake_loader_factory(route_probabilities()), agent)
    adapter = CleanedTableAdapter(CLEANED_FIXTURE, lineage_path=tmp_path / "cleaned-lineage.json")
    assert deps.confirmations is not None
    deps = replace(deps, tools=BankTools(adapter, deps.confirmations))

    try:
        final, _ = invoke(deps, "camilo", "Cancela mi transferencia pendiente")

        assert final["escalate_reason"] == "FC-INCOMPLETE-SOURCE"
        assert final["rule_id"] == "FC-INCOMPLETE-SOURCE"
        assert final["tool_results"][0].payload["amount"] is None
        assert final["tool_results"][0].payload["currency"] is None
        assert adapter.action_log == []
        assert deps.confirmations._granted == set()
        assert [(record.rule_id, record.verdict) for record in records_of(deps, Stage.GATE)] == [
            ("FC-INCOMPLETE-SOURCE", "block")
        ]
    finally:
        adapter.close()


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


def test_investigation_write_is_refused_outside_investigate(deps_factory, fake_loader_factory):
    """Decision 24: explain exposes reads only; open_investigation is refused by name.

    The act writes (request_cancellation, retry_payment) take a different
    path: they go through the Gate, as the act-stage tests below show.
    """
    agent = ScriptedAgent(
        [
            AgentDraft(
                tool_calls=(
                    ToolCall(
                        tool="open_investigation",
                        arguments={"entry_reference": "E-MX-002", "reason": "No llega el pago"},
                    ),
                )
            )
        ]
    )
    loader = fake_loader_factory(route_probabilities())
    deps = deps_factory(loader, agent)

    final, _ = invoke(deps, "ana", "Abre un caso con mi transferencia")

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


def test_act_allow_executes_with_token_and_read_back(deps_factory, fake_loader_factory):
    """The act stage: allow -> confirmation token -> write -> verified read-back."""
    agent = ScriptedAgent([AgentDraft(tool_calls=(CANCEL_CALL,)), AgentDraft(text=ACT_REPLY)])
    loader = fake_loader_factory(route_probabilities())
    deps = deps_factory(loader, agent)

    final, _ = invoke(deps, "ana", "Quiero cancelar mi transferencia pendiente")

    assert final["reply"] == ACT_REPLY
    assert not final.get("escalated")
    assert final["gate_verdict"] == "allow"
    assert final["read_backs"] == ["cancel_transfer"]
    tools_used = [result.tool for result in final["tool_results"]]
    assert tools_used == ["get_entry_detail", "request_cancellation", "get_payment_status"]
    # The token was issued for exactly this action and the tool consumed it.
    assert deps.confirmations is not None
    assert deps.confirmations._granted == set()
    gate_records = records_of(deps, Stage.GATE)
    assert [record.rule_id for record in gate_records] == ["GATE-ALLOW"]
    assert gate_records[0].verdict == "allow"
    # The reply claiming the cancellation passed the cascade on attempt 1.
    verifier_records = records_of(deps, Stage.VERIFIER)
    assert [record.verdict for record in verifier_records] == ["pass"]
    # FR-7: the action result card comes from the verified read-back.
    assert final["card"]["key"] == "action_result"
    assert final["card"]["payload"]["action"] == "request_cancellation"
    assert final["card"]["payload"]["entry_reference"] == "E-MX-002"
    assert final["card"]["payload"]["status"] == final["status"]


def test_retry_allow_executes_with_read_back(deps_factory, fake_loader_factory):
    """The retry write runs the same path over a declined payment."""
    agent = ScriptedAgent([AgentDraft(tool_calls=(RETRY_CALL,)), AgentDraft(text=RETRY_REPLY)])
    loader = fake_loader_factory(route_probabilities())
    deps = deps_factory(loader, agent)

    final, _ = invoke(deps, "dana", "Mi transferencia fue rechazada, ¿la pueden reintentar?")

    assert final["reply"] == RETRY_REPLY
    assert final["read_backs"] == ["retry_payment"]
    tools_used = [result.tool for result in final["tool_results"]]
    assert tools_used == ["get_entry_detail", "retry_payment", "get_payment_status"]


def test_act_ask_pauses_for_approval_and_resumes(deps_factory, fake_loader_factory):
    """The ask verdict pauses on interrupt(); an approval resumes and executes."""
    agent = ScriptedAgent([AgentDraft(tool_calls=(CANCEL_CALL,)), AgentDraft(text=ACT_REPLY)])
    # clear_enough 0.6 routes to the agents (>= 0.50) but is below the Gate's
    # 0.70: acting on a guess needs a person (GATE-UNCLEAR).
    loader = fake_loader_factory(route_probabilities(clear_enough={"clear": 0.6, "unclear": 0.4}))
    deps = deps_factory(loader, agent)
    graph = build_hub_graph(deps, checkpointer=InMemorySaver())
    issued, session_ref = deps.issuer.issue("ana")
    config = {"configurable": {"session_token": issued, "thread_id": "act-ask"}}

    paused = graph.invoke(
        {"persona": "ana", "session_ref": session_ref, "message": "Cancela mi transferencia"},
        config=config,
    )

    payload = paused["__interrupt__"][0].value
    assert payload["type"] == "approve_action"
    assert payload["action"] == "request_cancellation"
    assert payload["entry_reference"] == "E-MX-002"
    assert payload["amount"] == "5000.00"
    assert payload["currency"] == "MXN"
    assert payload["rule_id"] == "GATE-UNCLEAR"
    assert paused.get("reply") is None  # nothing went out while paused

    final = graph.invoke(Command(resume=True), config=config)

    assert final["reply"] == ACT_REPLY
    assert final["read_backs"] == ["cancel_transfer"]
    gate_records = records_of(deps, Stage.GATE)
    assert gate_records[0].rule_id == "GATE-UNCLEAR"
    assert gate_records[0].verdict == "ask"
    assert final["human_action"] is HumanAction.APPROVE_ACTION


def test_act_ask_denied_escalates(deps_factory, fake_loader_factory):
    """A denied approval escalates; the write never runs."""
    agent = ScriptedAgent([AgentDraft(tool_calls=(CANCEL_CALL,))])
    loader = fake_loader_factory(route_probabilities(clear_enough={"clear": 0.6, "unclear": 0.4}))
    deps = deps_factory(loader, agent)
    graph = build_hub_graph(deps, checkpointer=InMemorySaver())
    issued, session_ref = deps.issuer.issue("ana")
    config = {"configurable": {"session_token": issued, "thread_id": "act-deny"}}

    graph.invoke(
        {"persona": "ana", "session_ref": session_ref, "message": "Cancela mi transferencia"},
        config=config,
    )
    final = graph.invoke(Command(resume=False), config=config)

    assert final["escalated"] is True
    assert final["case_ref"].startswith("case-")
    assert all(result.tool != "request_cancellation" for result in final["tool_results"])
    human = records_of(deps, Stage.HUMAN)
    assert human[0].inputs_summary["reason"] == "APPROVAL-DENIED"


def test_act_block_names_and_logs_the_rule(deps_factory, fake_loader_factory):
    """A blocked action is refused naming the rule; the write never runs."""
    # E-MX-002 is Pending; a retry needs a Declined payment: GATE-INELIGIBLE.
    agent = ScriptedAgent(
        [
            AgentDraft(
                tool_calls=(
                    ToolCall(tool="retry_payment", arguments={"entry_reference": "E-MX-002"}),
                )
            )
        ]
    )
    loader = fake_loader_factory(route_probabilities())
    deps = deps_factory(loader, agent)

    final, _ = invoke(deps, "ana", "Reintenta mi transferencia")

    assert "GATE-INELIGIBLE" in final["reply"]
    assert final["card"] == {"key": "refusal", "payload": {"rule": "GATE-INELIGIBLE"}}
    gate_records = records_of(deps, Stage.GATE)
    assert gate_records[0].verdict == "block"
    assert all(result.tool != "retry_payment" for result in final["tool_results"])
    assert len(agent.requests) == 1  # the refusal ends the turn


def test_gate_refuses_other_customers_target(deps_factory, fake_loader_factory):
    """The Gate reads the target itself: another customer's entry is refused."""
    agent = ScriptedAgent(
        [
            AgentDraft(
                tool_calls=(
                    ToolCall(
                        tool="request_cancellation",
                        arguments={"entry_reference": "E-US-001"},
                    ),
                )
            )
        ]
    )
    loader = fake_loader_factory(route_probabilities())
    deps = deps_factory(loader, agent)

    final, _ = invoke(deps, "ana", "Cancela la transferencia E-US-001")

    assert "TOOL-NOT-OWNER" in final["reply"]
    assert "120.00" not in final["reply"] and "Dana" not in final["reply"]
    refusals = [
        record
        for record in records_of(deps, Stage.HARD_RULES)
        if record.rule_id == "TOOL-NOT-OWNER"
    ]
    assert len(refusals) == 1
    assert records_of(deps, Stage.GATE) == []  # ownership first: no verdict


def test_tool_side_fraud_flag_refuses_after_allow(deps_factory, fake_loader_factory):
    """Defense in depth: the tool's own fraud check refuses what the Gate allowed."""
    # E-AR-002 is Declined and fraud-flagged; without a FraudContext the Gate
    # sees no signal and allows, and the tool still refuses the write.
    agent = ScriptedAgent(
        [
            AgentDraft(
                tool_calls=(
                    ToolCall(tool="retry_payment", arguments={"entry_reference": "E-AR-002"}),
                )
            )
        ]
    )
    loader = fake_loader_factory(route_probabilities())
    deps = deps_factory(loader, agent)

    final, _ = invoke(deps, "lucia", "Reintenta mi transferencia rechazada")

    assert "TOOL-FRAUD-FLAGGED" in final["reply"]
    assert final["card"]["payload"]["rule"] == "TOOL-FRAUD-FLAGGED"
    gate_records = records_of(deps, Stage.GATE)
    assert gate_records[0].verdict == "allow"
    assert all(result.tool != "get_payment_status" for result in final["tool_results"])


def test_act_without_confirmation_issuer_fails_closed(deps_factory, fake_loader_factory):
    """No issuer, no write: an allowed action without a token path escalates."""
    agent = ScriptedAgent([AgentDraft(tool_calls=(CANCEL_CALL,))])
    loader = fake_loader_factory(route_probabilities())
    deps = deps_factory(loader, agent, with_confirmations=False)

    final, _ = invoke(deps, "ana", "Cancela mi transferencia")

    assert final["escalated"] is True
    assert all(result.tool != "request_cancellation" for result in final["tool_results"])
    human = records_of(deps, Stage.HUMAN)
    assert human[0].inputs_summary["reason"] == "FC-CONFIRMATIONS"


def test_investigate_opens_a_bank_case_for_the_focused_payment(deps_factory, fake_loader_factory):
    """A resumed thread that already found a payment opens a real bank case:
    the gate confirms the write (ask folds into the handoff), the bank's case
    id becomes the case ref, and the opening lands in the evidence."""
    agent = ScriptedAgent(
        [
            AgentDraft(tool_calls=(ENTRY_CALL,)),
            AgentDraft(text=GOOD_REPLY),
        ]
    )
    loader = fake_loader_factory(route_probabilities())
    deps = deps_factory(loader, agent)
    graph = build_hub_graph(deps, checkpointer=InMemorySaver())
    issued, session_ref = deps.issuer.issue("ana")
    config = {"configurable": {"thread_id": "t-case", "session_token": issued}}

    # Turn one: a normal explanation that focuses the pending payment.
    first = graph.invoke(
        {
            "persona": "ana",
            "session_ref": session_ref,
            "message": "¿Por qué mi transferencia sigue pendiente?",
        },
        config=config,
    )
    assert first["reply"] == GOOD_REPLY

    # Turn two on the same thread: the customer asks for a person, and the
    # investigate stage attaches the case to the focused payment.
    paused = graph.invoke(
        {
            "persona": "ana",
            "session_ref": session_ref,
            "message": "Quiero hablar con una persona",
        },
        config=config,
    )
    payload = paused["__interrupt__"][0].value
    assert payload["type"] == "operator_queue"
    assert payload["case_ref"].startswith("CASE-")  # the bank's own case id
    assert {"verified_fact": "get_entry_detail E-MX-002 -> Pending"} in payload["case_file"]

    final = graph.invoke(Command(resume="refunded manually"), config=config)

    assert final["escalated"] is True
    assert final["case_ref"] == payload["case_ref"]
    assert final["case_ref"] in final["reply"]
    assert any(result.tool == "open_investigation" for result in final["tool_results"])
    # The gate confirmed the write: one record, ask folded into the handoff.
    gate_records = records_of(deps, Stage.GATE)
    assert [record.verdict for record in gate_records] == ["ask"]
    assert gate_records[0].rule_id == "HR-ASKS-HUMAN"
    assert final["gate_verdict"] == "ask"
    assert final["action"] == "open_investigation"


def test_follow_up_stage_on_a_resumed_thread_with_an_open_case(deps_factory, fake_loader_factory):
    """A thread with an open case routes later questions to the follow-up
    stage: the agent sees the case ref (context, never a secret) and drafts
    under the follow-up tools."""
    follow_up_reply = "Una persona de nuestro equipo está revisando su caso."
    agent = ScriptedAgent([AgentDraft(text=follow_up_reply)])
    loader = fake_loader_factory(route_probabilities())  # scores always say agents
    deps = deps_factory(loader, agent)
    graph = build_hub_graph(deps, checkpointer=InMemorySaver())
    issued, session_ref = deps.issuer.issue("ana")
    config = {"configurable": {"thread_id": "t-follow", "session_token": issued}}

    # Turn one asks for a person; the resume clears the operator queue.
    paused = graph.invoke(
        {
            "persona": "ana",
            "session_ref": session_ref,
            "message": "Quiero hablar con una persona",
        },
        config=config,
    )
    case_ref = paused["case_ref"]
    graph.invoke(Command(resume="in progress"), config=config)

    # Turn two: an ordinary question on the same thread is a follow-up.
    final = graph.invoke(
        {
            "persona": "ana",
            "session_ref": session_ref,
            "message": "¿Cómo va mi caso?",
        },
        config=config,
    )

    assert final["stage"] == HubStage.FOLLOW_UP
    assert final["reply"] == follow_up_reply
    assert final["escalated"] is False  # the reply passed verification
    request = agent.requests[-1]
    assert request.stage == HubStage.FOLLOW_UP
    assert request.case_ref == case_ref


def test_investigate_honours_a_blocked_case_opening(deps_factory, fake_loader_factory):
    """The gate confirms open_investigation like every write: an Approved
    entry is ineligible (GATE-INELIGIBLE), so no bank case is opened — but
    the turn still reaches the operator queue with the file."""
    agent = ScriptedAgent(
        [
            AgentDraft(
                tool_calls=(
                    ToolCall(tool="get_entry_detail", arguments={"entry_reference": "E-MX-001"}),
                )
            ),
            AgentDraft(text="Su transferencia de 1500.00 MXN fue aprobada."),
        ]
    )
    loader = fake_loader_factory(route_probabilities())
    deps = deps_factory(loader, agent)
    graph = build_hub_graph(deps, checkpointer=InMemorySaver())
    issued, session_ref = deps.issuer.issue("ana")
    config = {"configurable": {"thread_id": "t-blocked-case", "session_token": issued}}

    # Turn one focuses E-MX-001 (Approved, 1500.00 MXN).
    first = graph.invoke(
        {
            "persona": "ana",
            "session_ref": session_ref,
            "message": "¿Cómo terminó mi transferencia de 1500?",
        },
        config=config,
    )
    assert first["reply"] == "Su transferencia de 1500.00 MXN fue aprobada."

    # Turn two asks for a person: opening a case on an Approved payment is
    # ineligible, so the gate blocks and no bank case is attached.
    paused = graph.invoke(
        {
            "persona": "ana",
            "session_ref": session_ref,
            "message": "Quiero hablar con una persona",
        },
        config=config,
    )
    payload = paused["__interrupt__"][0].value
    assert payload["type"] == "operator_queue"
    assert paused["case_ref"].startswith("case-")  # fallback: no bank case
    assert all(result.tool != "open_investigation" for result in paused["tool_results"])
    assert paused["gate_verdict"] == "block"
    gate_records = records_of(deps, Stage.GATE)
    assert [record.verdict for record in gate_records] == ["block"]
    assert gate_records[0].rule_id == "GATE-INELIGIBLE"

    final = graph.invoke(Command(resume="handled offline"), config=config)
    assert final["escalated"] is True
    assert final["case_ref"] in final["reply"]


def test_the_hub_hands_the_verifier_a_redacted_question(happy_deps, monkeypatch):
    """End to end: a real turn supplies the question the judge criterion depends on.

    Spies on the seam rather than the state, because the evidence is built inside the graph and
    never returned. The customer wrote "5000 pesos", the tool payload carries the amount, so the
    digest must keep the question while dropping the figure that already travels as evidence.
    """
    import calvino.hub.graph as graph_module

    seen: dict[str, Any] = {}
    original = graph_module.evidence_from_tool_results

    def spy(*args: Any, **kwargs: Any):
        evidence = original(*args, **kwargs)
        seen["question"] = evidence.customer_question
        return evidence

    monkeypatch.setattr(graph_module, "evidence_from_tool_results", spy)

    deps, _, _ = happy_deps
    final, _ = invoke(deps, "ana", "¿Por qué mi transferencia de 5000 pesos sigue pendiente?")

    assert final["route"] is Route.AGENTS, "the turn reached the verifier at all"
    assert seen["question"], "the verifier got no question, so question-fully-answered cannot pass"
    assert "pendiente" in seen["question"], "the substance of the question survives redaction"
    assert "5000" not in seen["question"], "the amount travels as evidence, not as prose"


def test_a_hub_without_a_judge_fails_closed_instead_of_approving(deps_factory, fake_loader_factory):
    """No silent stand-in judge: the unverified criteria escalate the reply to a person."""
    agent = ScriptedAgent([AgentDraft(tool_calls=(ENTRY_CALL,)), AgentDraft(text=GOOD_REPLY)])
    deps = deps_factory(fake_loader_factory(route_probabilities()), agent)
    deps = replace(deps, judge=None)
    final, _ = invoke(deps, "ana", "¿Qué pasó con mi transferencia?")
    assert final["escalated"] is True
    failed = {entry["criterion_id"]: entry["reason"] for entry in final["case_file"]}
    assert "question-fully-answered" in failed
    assert "unverified" in failed["question-fully-answered"]
