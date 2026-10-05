"""Integration tests for durable case persistence and process restart recovery (TSD-025, T-401)."""

from __future__ import annotations

import sqlite3

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver

from calvino.hub.agent import ScriptedAgent
from calvino.hub.service import HubService
from calvino.hub.storage import SqliteCaseStore
from calvino.records import Route


def _route_probabilities(**overrides: dict[str, float]) -> dict[str, dict[str, float]]:
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


def _make_deps(deps_factory, fake_loader_factory, agent=None):
    loader = fake_loader_factory(_route_probabilities())
    return deps_factory(loader, agent or ScriptedAgent([]))


def test_durable_case_persists_and_resumes_across_service_restart(
    deps_factory, fake_loader_factory, tmp_path
):
    """A parked turn can be resumed by its case reference after process restart (T-401)."""
    db_path = tmp_path / "checkpoints.sqlite"
    conn1 = sqlite3.connect(db_path, check_same_thread=False)
    checkpointer1 = SqliteSaver(conn1)
    checkpointer1.setup()

    case_store1 = SqliteCaseStore(tmp_path / "cases.sqlite")
    service1 = HubService(
        _make_deps(deps_factory, fake_loader_factory),
        checkpointer=checkpointer1,
        case_store=case_store1,
    )

    # 1. Park a turn via explicit human request
    parked = service1.handle_message("ana", "Quiero hablar con una persona")
    assert parked.awaiting == "operator_queue"
    assert parked.escalated is True
    assert parked.route == Route.HUMAN.value
    assert parked.case_ref is not None
    assert parked.awaiting_ref == parked.case_ref

    cases1 = service1.list_cases()
    assert any(c.case_ref == parked.case_ref for c in cases1)

    # 2. Simulate process death: delete service1 and its connection
    del service1
    del checkpointer1
    conn1.close()

    # 3. Simulate process restart: instantiate new service2 with same SQLite databases
    conn2 = sqlite3.connect(db_path, check_same_thread=False)
    checkpointer2 = SqliteSaver(conn2)
    case_store2 = SqliteCaseStore(tmp_path / "cases.sqlite")

    service2 = HubService(
        _make_deps(deps_factory, fake_loader_factory),
        checkpointer=checkpointer2,
        case_store=case_store2,
    )

    # 4. Verify case is visible in operator queue on service2
    cases2 = service2.list_cases()
    matched = next((c for c in cases2 if c.case_ref == parked.case_ref), None)
    assert matched is not None
    assert matched.status == "in_investigation"
    assert matched.persona == "ana"

    # 5. Resume the parked case on service2 with renewed trusted session authority
    resumed = service2.resume(
        parked.case_ref,
        "assigned to operator 7",
        actor_id="operator:restart-agent-01",
    )
    assert resumed.escalated is True
    assert resumed.case_ref == parked.case_ref

    # 6. Verify status updated to resolved in database
    cases_after = service2.list_cases()
    resolved_case = next(c for c in cases_after if c.case_ref == parked.case_ref)
    assert resolved_case.status == "resolved"


def test_durable_case_idempotency_prevents_duplicate_resume(
    deps_factory, fake_loader_factory, tmp_path
):
    """Resuming an already resolved case fails closed, preventing duplicate execution."""
    conn = sqlite3.connect(tmp_path / "chk.sqlite", check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    checkpointer.setup()
    case_store = SqliteCaseStore(tmp_path / "cases.sqlite")

    service = HubService(
        _make_deps(deps_factory, fake_loader_factory),
        checkpointer=checkpointer,
        case_store=case_store,
    )

    parked = service.handle_message("ana", "Quiero hablar con una persona")
    assert parked.case_ref is not None
    service.resume(parked.case_ref, "assigned to operator 7")

    # Second resume attempt must raise ValueError
    with pytest.raises(ValueError, match="already resolved"):
        service.resume(parked.case_ref, "Segunda resolución no permitida")


def test_no_raw_session_tokens_persisted_in_database(deps_factory, fake_loader_factory, tmp_path):
    """Security invariant (TSD-025): raw session tokens must never be written to SQLite."""
    cases_db = tmp_path / "cases_security.sqlite"
    case_store = SqliteCaseStore(cases_db)
    conn = sqlite3.connect(tmp_path / "chk_sec.sqlite", check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    checkpointer.setup()

    service = HubService(
        _make_deps(deps_factory, fake_loader_factory),
        checkpointer=checkpointer,
        case_store=case_store,
    )

    parked = service.handle_message("ana", "Quiero hablar con una persona")
    assert parked.case_ref is not None

    # Inspect the raw sqlite table
    raw_conn = sqlite3.connect(cases_db)
    cursor = raw_conn.execute("SELECT * FROM cases")
    columns = [desc[0] for desc in cursor.description]
    assert "token" not in columns
    assert "session_token" not in columns

    rows = cursor.fetchall()
    for row in rows:
        for val in row:
            if isinstance(val, str):
                assert "jwt" not in val.lower()
                assert "bearer" not in val.lower()
