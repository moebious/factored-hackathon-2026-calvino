"""Tests for calvino.hub.llm_agent (TSD-016): the model writes the reply, the harness plans.

No network: a scripted ``FakeChatClient`` stands in for the provider, so each test can assert
exactly what the model would have been sent and what the hub does with what it sends back.
"""

from __future__ import annotations

import pytest
from tests.calvino.hub.test_graph import ENTRY_CALL, invoke, records_of, route_probabilities

from calvino.hub import AgentRequest, HubStage, LlmAgent, ToolCall
from calvino.hub.llm_agent import MAX_REPLY_CHARS, AgentOutputError
from calvino.hub.playbook import load_playbook
from calvino.llm import ChatResponse, LlmUnavailable
from calvino.llm.contracts import Role
from calvino.records import Stage
from calvino.verifier.evidence import Evidence, ToolResult
from calvino.verifier.verdicts import CriterionVerdict

DETAIL = ToolResult(
    tool="get_entry_detail",
    payload={
        "entry_reference": "E-MX-002",
        "amount": "5000.00",
        "currency": "MXN",
        "status": "Pending",
        "booking_date": "2026-06-10",
        "value_date": "2026-06-11",
        "remittance_information": "Transfer to a friend",
    },
)
GOOD = "Su transferencia de 5000.00 MXN «Transfer to a friend» del 10/06/2026 está pendiente."


def explain_request(**kwargs) -> AgentRequest:
    return AgentRequest(
        stage=HubStage.EXPLAIN.value,
        message="¿Por qué sigue pendiente E-MX-002?",
        guidance=load_playbook().guidance("Pending"),
        tool_results=(DETAIL,),
        **kwargs,
    )


def agent_with(fake_chat_client_factory, reply: str = GOOD, **kwargs):
    client = fake_chat_client_factory({"agent-explain": reply}, **kwargs)
    return LlmAgent(client), client


def test_planner_tool_calls_make_no_model_call(fake_chat_client_factory) -> None:
    agent, client = agent_with(fake_chat_client_factory)
    draft = agent.draft(AgentRequest(stage="explain", message="¿Por qué sigue pendiente E-MX-002?"))
    assert draft.tool_calls == (
        ToolCall(tool="get_entry_detail", arguments={"entry_reference": "E-MX-002"}),
    )
    assert client.requests == []


def test_fixed_replies_without_a_payload_make_no_model_call(fake_chat_client_factory) -> None:
    agent, client = agent_with(fake_chat_client_factory)
    no_listing_entries = ToolResult(tool="list_problem_transactions", payload={"entries": []})
    draft = agent.draft(
        AgentRequest(stage="explain", message="mi pago", tool_results=(no_listing_entries,))
    )
    assert draft.text and "No encontré" in draft.text
    assert client.requests == []


def test_a_payload_step_asks_the_model_once_with_grounded_context(
    fake_chat_client_factory,
) -> None:
    agent, client = agent_with(fake_chat_client_factory, prompt_tokens=120, completion_tokens=40)
    evidence = Evidence(customer_question="¿Por qué sigue pendiente?")
    draft = agent.draft(explain_request(evidence=evidence))

    assert draft.text == GOOD
    assert len(client.requests) == 1
    sent = client.requests[0]
    assert sent.role is Role.AGENT and sent.purpose == "agent-explain"
    assert sent.temperature == 0.0 and sent.seed is not None and sent.max_tokens >= 1024
    system, user = (message.content for message in sent.messages)
    assert "Spanish" in system
    assert "5000.00" in user and "E-MX-002" in user  # the verified record
    assert "settlement on the value" in user  # the playbook guidance for Pending
    assert "¿Por qué sigue pendiente?" in user  # the redacted digest, not the raw message
    assert "E-MX-002?" not in user  # the raw message is never sent
    # The meter the runner reads: one response, then drained.
    assert [r.prompt_tokens for r in agent.drain_responses()] == [120]
    assert agent.drain_responses() == []


def test_the_prompt_uses_the_customers_language(fake_chat_client_factory) -> None:
    agent, client = agent_with(fake_chat_client_factory)
    agent.draft(explain_request(evidence=Evidence(customer_language="pt")))
    assert "Portuguese" in client.requests[0].messages[0].content


def test_feedback_reaches_the_retry_prompt(fake_chat_client_factory) -> None:
    agent, client = agent_with(fake_chat_client_factory)
    feedback = CriterionVerdict(
        criterion_id="amounts-dates-merchants-match",
        passed=False,
        checker="code",
        reason="9999.99 is not in the record",
    )
    agent.draft(explain_request(feedback=(feedback,)))
    user = client.requests[0].messages[1].content
    assert "amounts-dates-merchants-match" in user and "9999.99 is not in the record" in user


def test_no_tool_result_outside_the_stage_reaches_the_model(fake_chat_client_factory) -> None:
    other = ToolResult(tool="list_problem_transactions", payload={"entries": [{"x": "LEAK-1"}]})
    agent, client = agent_with(fake_chat_client_factory)
    request = explain_request().model_copy(update={"tool_results": (other, DETAIL)})
    agent.draft(request)
    assert "LEAK-1" not in client.requests[0].messages[1].content


def test_an_executed_write_is_an_act_reply_even_from_the_explain_stage(
    fake_chat_client_factory,
) -> None:
    write = ToolResult(tool="request_cancellation", payload={"outcome": "Accepted"})
    read_back = ToolResult(
        tool="get_payment_status", payload={"original_reference": "E-MX-002", "status": "Reversed"}
    )
    client = fake_chat_client_factory({"agent-act": GOOD})
    agent = LlmAgent(client)
    request = AgentRequest(
        stage="explain",
        message="cancela E-MX-002",
        tool_results=(DETAIL, write, read_back),
    )
    assert agent.draft(request).text == GOOD
    assert client.requests[0].purpose == "agent-act"


@pytest.mark.parametrize(
    "reply, why",
    [
        ("", "empty"),
        ("   \n", "empty"),
        ("x" * (MAX_REPLY_CHARS + 1), "characters"),
        ("```json\n{}\n```", "dialect"),
        ('<tool_call>{"name": "retry_payment"}</tool_call>', "dialect"),
    ],
)
def test_guards_reject_non_replies(fake_chat_client_factory, reply, why) -> None:
    agent, _ = agent_with(fake_chat_client_factory, reply)
    with pytest.raises(AgentOutputError, match=why if why != "empty" else "empty"):
        agent.draft(explain_request())


def test_a_truncated_reply_is_rejected() -> None:
    class Truncating:
        def complete(self, request):
            return ChatResponse(text="Su transferencia", model="m", finish_reason="length")

    with pytest.raises(AgentOutputError, match="cut off"):
        LlmAgent(Truncating()).draft(explain_request())


def test_a_provider_error_propagates_without_a_template_fallback() -> None:
    class Down:
        def complete(self, request):
            raise LlmUnavailable("provider down")

    with pytest.raises(LlmUnavailable):
        LlmAgent(Down()).draft(explain_request())


# -- through the hub ------------------------------------------------------------------------


class _ScriptedModel:
    """Replies in order, then raises: a drifting test fails loudly."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        if not self.replies:
            raise LlmUnavailable("no scripted reply left")
        reply = self.replies.pop(0)
        return ChatResponse(text=reply, model="scripted", finish_reason="stop")


def test_the_hub_passes_a_grounded_model_reply(deps_factory, fake_loader_factory) -> None:
    model = _ScriptedModel([GOOD])
    deps = deps_factory(fake_loader_factory(route_probabilities()), LlmAgent(model))
    final, _ = invoke(deps, "ana", "¿Por qué mi transferencia sigue pendiente? E-MX-002")
    assert final["reply"] == GOOD and not final.get("escalated")
    assert len(model.requests) == 1  # tools were planned by the harness, not the model
    assert ENTRY_CALL.tool in {r.tool for r in final["tool_results"]}


def test_a_wrong_amount_is_retried_once_then_passes(deps_factory, fake_loader_factory) -> None:
    model = _ScriptedModel(["Su pago de 9999.99 MXN está pendiente.", GOOD])
    deps = deps_factory(fake_loader_factory(route_probabilities()), LlmAgent(model))
    final, _ = invoke(deps, "ana", "¿Por qué mi transferencia sigue pendiente? E-MX-002")
    assert final["reply"] == GOOD
    assert "amounts-dates-merchants-match" in model.requests[1].messages[1].content
    assert [r.verdict for r in records_of(deps, Stage.VERIFIER)] == ["fail", "pass"]


def test_two_wrong_replies_escalate(deps_factory, fake_loader_factory) -> None:
    bad = "Su pago de 9999.99 MXN está pendiente."
    deps = deps_factory(
        fake_loader_factory(route_probabilities()), LlmAgent(_ScriptedModel([bad, bad]))
    )
    final, _ = invoke(deps, "ana", "¿Por qué mi transferencia sigue pendiente? E-MX-002")
    assert final["escalated"] is True and final["case_ref"].startswith("case-")


def test_a_provider_failure_escalates_as_agent_error(deps_factory, fake_loader_factory) -> None:
    deps = deps_factory(fake_loader_factory(route_probabilities()), LlmAgent(_ScriptedModel([])))
    final, _ = invoke(deps, "ana", "¿Por qué mi transferencia sigue pendiente? E-MX-002")
    assert final["escalated"] is True
    assert records_of(deps, Stage.HUMAN)[0].inputs_summary["reason"] == "AGENT-ERROR"


def test_the_session_token_never_reaches_the_model(deps_factory, fake_loader_factory) -> None:
    model = _ScriptedModel([GOOD])
    deps = deps_factory(fake_loader_factory(route_probabilities()), LlmAgent(model))
    _, token = invoke(deps, "ana", "¿Por qué mi transferencia sigue pendiente? E-MX-002")
    sent = " ".join(m.content for r in model.requests for m in r.messages)
    assert token not in sent
