"""Tests for durable case storage (TSD-025, T-401)."""

from __future__ import annotations

import pytest

from calvino.hub.storage import (
    CaseRecord,
    MemoryCaseStore,
    SqliteCaseStore,
    create_case_store,
)


def _sample_case(case_ref: str = "CASE-TEST-001", awaiting_ref: str = "REF-001") -> CaseRecord:
    return CaseRecord(
        case_ref=case_ref,
        thread_id="persona-ana",
        persona="ana",
        status="pending_approval",
        reason_rule_id="GATE-AMOUNT-LIMIT",
        created_at="2026-10-05T07:00:00Z",
        customer_message="Por favor aprueba mi reintento de pago.",
        entry_reference="TX-12345",
        amount="15000.00",
        currency="MXN",
        target_action="retry_payment",
        awaiting_ref=awaiting_ref,
        gate_verdict="ask",
    )


@pytest.mark.parametrize("store_cls", [MemoryCaseStore, None])
def test_case_store_put_and_get(tmp_path, store_cls):
    """Stores and retrieves a case record by case_ref and awaiting_ref."""
    if store_cls is None:
        store = SqliteCaseStore(tmp_path / "test-cases.sqlite")
    else:
        store = store_cls()

    case = _sample_case()
    store.put(case)

    by_ref = store.get_by_ref("REF-001")
    assert by_ref is not None
    assert by_ref.case_ref == "CASE-TEST-001"
    assert by_ref.thread_id == "persona-ana"
    assert by_ref.amount == "15000.00"

    by_case_ref = store.get_by_case_ref("CASE-TEST-001")
    assert by_case_ref is not None
    assert by_case_ref.awaiting_ref == "REF-001"


def test_sqlite_case_store_persists_across_instances(tmp_path):
    """Records persisted in SQLite remain available in a new store instance."""
    db_file = tmp_path / "durable.sqlite"
    store1 = SqliteCaseStore(db_file)
    store1.put(_sample_case("CASE-ANA-01", "REF-ANA-01"))
    store1.put(_sample_case("CASE-LUCIA-02", "REF-LUCIA-02"))

    # Destroy store1, open store2
    del store1
    store2 = SqliteCaseStore(db_file)

    cases = store2.list_all()
    assert len(cases) == 2
    refs = [c.case_ref for c in cases]
    assert "CASE-ANA-01" in refs
    assert "CASE-LUCIA-02" in refs

    matched = store2.get_by_ref("REF-LUCIA-02")
    assert matched is not None
    assert matched.case_ref == "CASE-LUCIA-02"


def test_case_store_update_status(tmp_path):
    """Updating status transitions the case state durably."""
    store = SqliteCaseStore(tmp_path / "status.sqlite")
    case = _sample_case()
    store.put(case)

    store.update_status(case.case_ref, "resolved")
    updated = store.get_by_case_ref(case.case_ref)
    assert updated is not None
    assert updated.status == "resolved"


def test_create_case_store_environment_fallback(monkeypatch, tmp_path):
    """create_case_store selects SQLite when CALVINO_DATA_DIR is set, else Memory."""
    monkeypatch.delenv("CALVINO_DATA_DIR", raising=False)
    mem_store = create_case_store()
    assert isinstance(mem_store, MemoryCaseStore)

    monkeypatch.setenv("CALVINO_DATA_DIR", str(tmp_path))
    sql_store = create_case_store()
    assert isinstance(sql_store, SqliteCaseStore)
