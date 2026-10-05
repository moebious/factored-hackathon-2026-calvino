"""Tests of the hub service facade (TSD-009): messages in, replies out.

Same fakes as the graph tests: a scripted loader and ``ScriptedAgent`` over
the synthetic bank fixture, with an in-memory checkpointer unless a test
points ``CALVINO_DATA_DIR`` at a temporary directory. Covered here: the
happy path, both parked-turn kinds (operator queue and action approval)
with their resumes, the fail-closed unknown ref, follow-up turns on a
thread with an open case, and the checkpointer defaults.
"""

from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from calvino.hub import (
    AgentDraft,
    HubService,
    HubStage,
    ScriptedAgent,
    ToolCall,
)
from calvino.records import Route

# The same grounded replies the graph tests use: every amount, date,
# merchant and status they state comes from the fixture's E-MX-002.
GOOD_REPLY = "Su transferencia de 5000.00 MXN «Transfer to a friend» del 10/06/2026 está pendiente."
ACT_REPLY = "He cancelado su transferencia de 5000.00 MXN «Transfer to a friend»."
FOLLOW_UP_REPLY = "Una persona de nuestro equipo está revisando su caso."

ENTRY_CALL = ToolCall(tool="get_entry_detail", arguments={"entry_reference": "E-MX-002"})
CANCEL_CALL = ToolCall(tool="request_cancellation", arguments={"entry_reference": "E-MX-002"})


def route_probabilities(**overrides: dict[str, float]) -> dict[str, dict[str, float]]:
    """Scripted Laya probabilities that route to the agents, with overrides.

    A local copy of the graph tests' helper: the service tests script the
    same System One seam, and test modules are not importable packages.
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


def make_service(deps_factory, fake_loader_factory, agent, **probability_overrides):
    """A service on an in-memory checkpointer with scripted probabilities."""
    loader = fake_loader_factory(route_probabilities(**probability_overrides))
    return HubService(deps_factory(loader, agent), checkpointer=InMemorySaver())


def test_handle_message_happy_path(deps_factory, fake_loader_factory):
    """One call runs the whole turn: verified reply, route, no escalation."""
    agent = ScriptedAgent([AgentDraft(tool_calls=(ENTRY_CALL,)), AgentDraft(text=GOOD_REPLY)])
    service = make_service(deps_factory, fake_loader_factory, agent)

    reply = service.handle_message("ana", "¿Por qué mi transferencia sigue pendiente?")

    assert reply.reply == GOOD_REPLY
    assert reply.route == Route.AGENTS.value
    assert reply.escalated is False
    assert reply.awaiting is None
    assert reply.case_ref is None


def test_reply_carries_the_turns_trace(deps_factory, fake_loader_factory):
    """The glass box reads the trace: this turn's decision records, in order."""
    agent = ScriptedAgent([AgentDraft(tool_calls=(ENTRY_CALL,)), AgentDraft(text=GOOD_REPLY)])
    service = make_service(deps_factory, fake_loader_factory, agent)

    reply = service.handle_message("ana", "¿Por qué mi transferencia sigue pendiente?")

    assert reply.trace, "the turn logged decisions, so the trace is not empty"
    route_step = next(step for step in reply.trace if step.stage == "classifier")
    assert route_step.rule_id == "RT-ACT"
    assert route_step.verdict == Route.AGENTS.value
    assert route_step.scores  # the calibrated probabilities the panel shows
    assert [step.stage for step in reply.trace] == ["classifier", "verifier"]


def test_resume_trace_covers_only_the_resumed_turn(deps_factory, fake_loader_factory):
    """A resumed turn's trace starts fresh: no replay of the parked turn."""
    agent = ScriptedAgent([])  # no agent step on the human route
    service = make_service(deps_factory, fake_loader_factory, agent)

    parked = service.handle_message("ana", "Quiero hablar con una persona")
    assert [step.rule_id for step in parked.trace] == ["HR-ASKS-HUMAN"]

    final = service.resume(parked.awaiting_ref, "assigned to operator 7")

    assert [step.stage for step in final.trace] == ["human"]
    assert final.trace[0].rule_id == "HR-ASKS-HUMAN"


def test_operator_queue_parks_and_resumes(deps_factory, fake_loader_factory):
    """The human route parks on the operator queue and resume closes it."""
    agent = ScriptedAgent([])  # no agent step on the human route
    service = make_service(deps_factory, fake_loader_factory, agent)

    parked = service.handle_message("ana", "Quiero hablar con una persona")

    assert parked.awaiting == "operator_queue"
    assert parked.escalated is True
    assert parked.route == Route.HUMAN.value
    assert parked.case_ref is not None and parked.case_ref.startswith("case-")
    assert parked.awaiting_ref == parked.case_ref  # the ref the operator holds

    final = service.resume(parked.awaiting_ref, "assigned to operator 7")

    assert final.escalated is True
    assert final.case_ref == parked.case_ref
    assert final.case_ref in final.reply
    assert final.card == {"key": "case_opened", "payload": {"case_ref": parked.case_ref}}


def test_approval_parks_and_resumes(deps_factory, fake_loader_factory):
    """An ask verdict parks for approval; approving runs the write."""
    agent = ScriptedAgent([AgentDraft(tool_calls=(CANCEL_CALL,)), AgentDraft(text=ACT_REPLY)])
    # clear_enough 0.6 routes to the agents but is below the Gate's 0.70:
    # acting on a guess needs a person (GATE-UNCLEAR).
    service = make_service(
        deps_factory, fake_loader_factory, agent, clear_enough={"clear": 0.6, "unclear": 0.4}
    )

    parked = service.handle_message("ana", "Cancela mi transferencia")

    assert parked.awaiting == "approve_action"
    assert parked.awaiting_ref == "persona-ana"  # approvals carry the thread ref
    assert parked.case_ref is None
    assert parked.reply == ""  # nothing went out while paused
    # FR-7: the operator (or the app) sees the confirmation card, mapped
    # from the Gate's payload — the bank's own numbers.
    assert parked.card == {
        "key": "action_confirmation",
        "payload": {
            "action": "request_cancellation",
            "entry_reference": "E-MX-002",
            "amount": "5000.00",
            "currency": "MXN",
        },
    }

    final = service.resume(parked.awaiting_ref, True)

    assert final.reply == ACT_REPLY
    assert final.escalated is False
    assert final.route == Route.AGENTS.value


def test_denied_approval_escalates(deps_factory, fake_loader_factory):
    """A denied approval escalates; the write never runs."""
    agent = ScriptedAgent([AgentDraft(tool_calls=(CANCEL_CALL,))])
    service = make_service(
        deps_factory, fake_loader_factory, agent, clear_enough={"clear": 0.6, "unclear": 0.4}
    )

    parked = service.handle_message("ana", "Cancela mi transferencia")
    final = service.resume(parked.awaiting_ref, False)

    assert final.escalated is True
    assert final.case_ref is not None
    assert final.case_ref in final.reply


def test_resume_unknown_ref_raises(deps_factory, fake_loader_factory):
    """An unknown ref raises instead of guessing a thread (fail closed)."""
    service = make_service(deps_factory, fake_loader_factory, ScriptedAgent([]))

    with pytest.raises(KeyError):
        service.resume("case-does-not-exist", "whatever")


def test_second_message_on_the_same_thread_follows_up(deps_factory, fake_loader_factory):
    """A thread with an open case routes the next message to follow-up."""
    agent = ScriptedAgent([AgentDraft(text=FOLLOW_UP_REPLY)])
    service = make_service(deps_factory, fake_loader_factory, agent)

    parked = service.handle_message("ana", "Quiero hablar con una persona")
    service.resume(parked.awaiting_ref, "in progress")
    follow = service.handle_message("ana", "¿Cómo va mi caso?")

    assert follow.reply == FOLLOW_UP_REPLY
    assert follow.escalated is False
    request = agent.requests[-1]
    assert request.stage == HubStage.FOLLOW_UP
    assert request.case_ref == parked.case_ref


def test_default_checkpointer_uses_the_data_dir(
    deps_factory, fake_loader_factory, tmp_path, monkeypatch
):
    """With CALVINO_DATA_DIR set the checkpointer is sqlite under it."""
    monkeypatch.setenv("CALVINO_DATA_DIR", str(tmp_path))
    agent = ScriptedAgent([AgentDraft(tool_calls=(ENTRY_CALL,)), AgentDraft(text=GOOD_REPLY)])
    loader = fake_loader_factory(route_probabilities())
    service = HubService(deps_factory(loader, agent))

    reply = service.handle_message("ana", "¿Por qué mi transferencia sigue pendiente?")

    assert reply.reply == GOOD_REPLY
    assert (tmp_path / "hub-checkpoints.sqlite").exists()


def test_default_checkpointer_falls_back_to_memory(deps_factory, fake_loader_factory, monkeypatch):
    """Without CALVINO_DATA_DIR the service still works, on memory."""
    monkeypatch.delenv("CALVINO_DATA_DIR", raising=False)
    agent = ScriptedAgent([AgentDraft(tool_calls=(ENTRY_CALL,)), AgentDraft(text=GOOD_REPLY)])
    loader = fake_loader_factory(route_probabilities())
    service = HubService(deps_factory(loader, agent))

    reply = service.handle_message("ana", "¿Por qué mi transferencia sigue pendiente?")

    assert reply.reply == GOOD_REPLY


def test_list_cases_empty_returns_fallback_seeds(deps_factory, fake_loader_factory):
    """An empty service returns seeded fallback cases for demo reliability (TSD-023)."""
    service = make_service(deps_factory, fake_loader_factory, ScriptedAgent([]))
    cases = service.list_cases()
    assert len(cases) >= 2
    refs = [c.case_ref for c in cases]
    assert "CASE-ANA-001" in refs
    assert "CASE-LUCIA-002" in refs


def test_list_cases_tracks_parked_turn(deps_factory, fake_loader_factory):
    """A parked turn appears in the operator queue with active status."""
    service = make_service(deps_factory, fake_loader_factory, ScriptedAgent([]))
    parked = service.handle_message("ana", "Quiero hablar con una persona")
    assert parked.escalated is True

    cases = service.list_cases()
    refs = [c.case_ref for c in cases]
    assert parked.case_ref in refs
    matched = next(c for c in cases if c.case_ref == parked.case_ref)
    assert matched.persona == "ana"
    assert matched.status == "in_investigation"


def test_resume_gate_block_raises_value_error(deps_factory, fake_loader_factory):
    """Safety invariant (decision 37): human operator cannot approve a Gate block."""
    service = make_service(deps_factory, fake_loader_factory, ScriptedAgent([]))
    with pytest.raises(ValueError, match="cannot approve action with Gate block"):
        service.resume("CASE-CARLOS-003", True)


def test_resume_fallback_seed_records_audit_log(deps_factory, fake_loader_factory):
    """Resuming a fallback seed updates status, returns reply, and logs human decision."""
    service = make_service(deps_factory, fake_loader_factory, ScriptedAgent([]))
    reply = service.resume("CASE-LUCIA-002", True, actor_id="operator:test-user")
    assert "approved" in reply.reply.lower()

    cases = service.list_cases()
    matched = next(c for c in cases if c.case_ref == "CASE-LUCIA-002")
    assert matched.status == "resolved"
