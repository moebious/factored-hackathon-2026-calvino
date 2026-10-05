"""MCP server tests (TSD-002): the server starts, exposes the ten tools, and takes the customer
from the hub-attached session, never from an argument the model controls."""

from __future__ import annotations

import json

import anyio
from mcp.client import Client
from tests.calvino.tools.conftest import Env

from calvino.tools import TOOL_NAMES, Session, create_server


def call(env: Env, session: Session | None, name: str, args: dict | None = None):
    server = create_server(env.tools, lambda ctx: session)

    async def run():
        async with Client(server) as client:
            return await client.call_tool(name, args or {})

    return anyio.run(run)


def text(result) -> str:
    return result.content[0].text


def listed(env: Env):
    server = create_server(env.tools, lambda ctx: None)

    async def run():
        async with Client(server) as client:
            return (await client.list_tools()).tools

    return anyio.run(run)


def test_the_server_starts_and_lists_the_ten_tools(dataset_env: Env) -> None:
    tools = listed(dataset_env)
    assert sorted(t.name for t in tools) == sorted(TOOL_NAMES) and len(tools) == 10


def test_no_tool_schema_exposes_a_session_or_customer(dataset_env: Env) -> None:
    for tool in listed(dataset_env):
        names = set(tool.input_schema.get("properties", {}))
        assert not {n for n in names if "session" in n or "customer" in n}, tool.name


def test_the_customer_comes_from_the_session(dataset_env: Env) -> None:
    result = call(dataset_env, dataset_env.session("C-MX-001"), "get_customer_summary")
    assert not result.is_error
    assert json.loads(text(result))["customer_id"] == "C-MX-001"


def test_a_customer_argument_chosen_by_the_model_is_ignored(dataset_env: Env) -> None:
    s = dataset_env.session("C-MX-001")
    result = call(
        dataset_env,
        s,
        "get_customer_summary",
        {"customer_id": "C-CO-001", "session_customer_id": "C-CO-001"},
    )
    assert json.loads(text(result))["customer_id"] == "C-MX-001"
    other = call(
        dataset_env,
        s,
        "get_entry_detail",
        {"entry_reference": "E-CO-001", "customer_id": "C-CO-001"},
    )
    assert other.is_error and "TOOL-NOT-OWNER" in text(other)


def test_a_refusal_reaches_the_client_with_its_rule_id(dataset_env: Env) -> None:
    result = call(
        dataset_env,
        dataset_env.session("C-MX-001"),
        "get_entry_detail",
        {"entry_reference": "E-NOPE"},
    )
    assert result.is_error and "TOOL-NOT-FOUND" in text(result)


def test_no_session_attached_is_refused(dataset_env: Env) -> None:
    result = call(dataset_env, None, "list_accounts")
    assert result.is_error and "TOOL-NO-SESSION" in text(result)


def test_a_write_over_mcp_needs_and_uses_the_token(dataset_env: Env) -> None:
    s = dataset_env.session("C-MX-001")
    args = {"entry_reference": "E-MX-002", "idempotency_key": "k", "confirmation_token": "forged"}
    refused = call(dataset_env, s, "request_cancellation", args)
    assert refused.is_error and "TOOL-TOKEN-INVALID" in text(refused)
    args["confirmation_token"] = dataset_env.token("C-MX-001", "request_cancellation", "E-MX-002")
    done = call(dataset_env, s, "request_cancellation", args)
    assert not done.is_error
    body = json.loads(text(done))
    assert body["outcome"] == "accepted" and body["simulated"] is True


def test_a_list_tool_returns_the_customers_entries(dataset_env: Env) -> None:
    result = call(dataset_env, dataset_env.session("C-CO-001"), "list_problem_transactions")
    assert not result.is_error
    refs = {e["entry_reference"] for e in result.structured_content["result"]}
    assert refs == {"E-CO-001", "E-CO-002", "E-CO-003"}
