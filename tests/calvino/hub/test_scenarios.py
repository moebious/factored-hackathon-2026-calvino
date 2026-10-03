"""Seeded acceptance scenarios (decision 23, TSD-009).

Every file in tests/scenarios/ is one acceptance criterion as data: the
persona, the message, scripted System 1 probabilities, a scripted agent,
and the expected outcome (route, reply, card, executed tool calls, log
records, and for AC-8 the replayed verdict). The runner executes each
scenario end-to-end over the bank fixture on every pytest run and feeds
the scoreboard the terminal summary prints: a scenario that passes is
never allowed to fail again.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from calvino.hub import AgentDraft, ScriptedAgent, ToolCall, build_hub_graph
from calvino.policy import replay_decision
from calvino.records import Route, Stage

SCENARIOS_DIR = Path(__file__).resolve().parents[2] / "scenarios"


def scenario_files() -> list[Path]:
    """All seeded scenarios, sorted by file name (AC-1 first)."""
    return sorted(SCENARIOS_DIR.glob("*.json"))


def _draft(step: dict[str, Any]) -> AgentDraft:
    """One scripted agent step: either a text draft or tool calls."""
    if "text" in step:
        return AgentDraft(text=step["text"])
    return AgentDraft(tool_calls=tuple(ToolCall(**call) for call in step["tool_calls"]))


@pytest.mark.parametrize("path", scenario_files(), ids=lambda path: path.stem)
def test_scenario(path, deps_factory, fake_loader_factory, scenario_scoreboard):
    """Run one seeded scenario end-to-end and assert its expected outcome."""
    scenario = json.loads(path.read_text(encoding="utf-8"))
    agent = ScriptedAgent([_draft(step) for step in scenario.get("agent_script", [])])
    loader = fake_loader_factory(scenario["probabilities"])
    deps = deps_factory(loader, agent)
    graph = build_hub_graph(deps, checkpointer=InMemorySaver())
    token, session_ref = deps.issuer.issue(scenario["persona"])
    config = {"configurable": {"thread_id": scenario["id"], "session_token": token}}

    state = graph.invoke(
        {
            "persona": scenario["persona"],
            "session_ref": session_ref,
            "message": scenario["message"],
        },
        config=config,
    )
    expected = scenario["expected"]
    if "awaiting" in expected:
        interrupts = state.get("__interrupt__") or ()
        assert interrupts, "the scenario expected a parked turn"
        assert interrupts[0].value["type"] == expected["awaiting"]
    if "resume" in scenario:
        state = graph.invoke(Command(resume=scenario["resume"]), config=config)

    route = state.get("route")
    assert route is not None and route.value == expected["route"]
    if "reply" in expected:
        assert state.get("reply") == expected["reply"]
    for fragment in expected.get("reply_contains", []):
        assert fragment in str(state.get("reply"))
    if expected.get("reply_contains_case_ref"):
        assert state.get("case_ref") in str(state.get("reply"))
    if "escalated" in expected:
        assert bool(state.get("escalated")) is expected["escalated"]
    if "card" in expected:
        card = state.get("card")
        assert card is not None and card["key"] == expected["card"]["key"]
        if "payload" in expected["card"]:
            assert card["payload"] == expected["card"]["payload"]
    if "tool_calls" in expected:
        executed = [result.tool for result in state.get("tool_results", [])]
        for tool in expected["tool_calls"]:
            assert tool in executed
    for wanted in expected.get("log_records", []):
        assert any(
            record.stage is Stage(wanted["stage"])
            and record.rule_id == wanted["rule_id"]
            and ("verdict" not in wanted or record.verdict == wanted["verdict"])
            for record in deps.log
        ), f"missing log record {wanted}"
    if "replay" in expected:
        record = next(r for r in deps.log if r.stage is Stage.CLASSIFIER)
        replayed = replay_decision(record, deps.policy)
        assert replayed.route is Route(expected["replay"]["route"])
        assert replayed.rule_id == expected["replay"]["rule_id"]

    scenario_scoreboard.append(f"{scenario['id']}: green ({scenario['title']})")
