"""Tests for calvino.hub.agent: the support agent interface and the scripted fake."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from calvino.hub.agent import AgentDraft, AgentRequest, ScriptedAgent, ToolCall


def test_tool_call_needs_a_tool_name() -> None:
    with pytest.raises(ValidationError):
        ToolCall(tool="")


def test_draft_needs_text_or_tool_calls() -> None:
    with pytest.raises(ValidationError, match="needs text, tool calls"):
        AgentDraft()


def test_draft_accepts_both_forms() -> None:
    assert AgentDraft(text="hola").tool_calls == ()
    assert AgentDraft(tool_calls=(ToolCall(tool="get_payment_status"),)).text is None


def test_request_defaults_are_inert() -> None:
    request = AgentRequest(stage="explain", message="where is my money?")
    assert request.evidence is None
    assert request.guidance is None
    assert request.feedback == ()


def test_models_are_frozen_and_closed() -> None:
    draft = AgentDraft(text="hola")
    with pytest.raises(ValidationError):
        draft.text = "adios"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        AgentRequest(stage="explain", message="x", unknown="y")  # type: ignore[call-arg]


def test_scripted_agent_returns_drafts_in_order() -> None:
    agent = ScriptedAgent([AgentDraft(text="one"), AgentDraft(text="two")])
    first = agent.draft(AgentRequest(stage="explain", message="a"))
    second = agent.draft(AgentRequest(stage="explain", message="b"))
    assert (first.text, second.text) == ("one", "two")


def test_scripted_agent_records_every_request() -> None:
    agent = ScriptedAgent([AgentDraft(text="x")])
    request = AgentRequest(stage="clarify", message="hola")
    agent.draft(request)
    assert agent.requests == [request]


def test_exhausted_script_raises() -> None:
    # Fail loudly, never drift into a fallback: the hub escalates on agent errors.
    agent = ScriptedAgent([])
    with pytest.raises(RuntimeError, match="no draft left"):
        agent.draft(AgentRequest(stage="explain", message="a"))
