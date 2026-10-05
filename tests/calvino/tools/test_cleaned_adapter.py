"""T-206 cleaned-table adapter tests use only the checked-in synthetic CSV fixture."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest
from tests.calvino.tools.conftest import build_env

from calvino.tools import CleanedTableAdapter, ConfigurationError, Rule, ToolRefusal

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "cleaned_bank"


@pytest.fixture
def cleaned_adapter(tmp_path):
    adapter = CleanedTableAdapter(
        FIXTURE,
        lineage_path=tmp_path / "lineage.json",
        clock=lambda: datetime(2026, 7, 1, tzinfo=UTC),
    )
    yield adapter
    adapter.close()


def test_customer_and_product_projection_keeps_missing_facts_null(cleaned_adapter):
    from calvino.tools.session import Session

    session = Session(customer_id="C-MX-001", expires_at="2026-07-02T00:00:00+00:00")
    summary = cleaned_adapter.get_customer_summary(session)
    products = cleaned_adapter.list_accounts(session)

    assert summary.customer_id == "C-MX-001"
    assert summary.country == "MX"
    assert summary.display_name is None
    assert summary.account_count is None
    assert len(products) == 1
    assert products[0].account_id == "P-MX-001"
    assert products[0].balance is None
    assert products[0].status is None


def test_transaction_reads_preserve_status_nulls_and_currency(cleaned_adapter):
    from calvino.tools.session import Session

    session = Session(customer_id="C-CO-001", expires_at="2026-07-02T00:00:00+00:00")
    entry = cleaned_adapter.get_entry_detail(session, "E-CO-002")
    payment = cleaned_adapter.get_payment_status(session, "E-CO-002")

    assert entry.status.value == "Pending"
    assert payment.status.value == "Pending"
    assert entry.amount is None
    assert entry.currency is None
    assert cleaned_adapter.get_entry_record(session, "E-CO-002").account_id is None
    assert entry.booking_date.isoformat() == "2026-06-14"

    entries = cleaned_adapter.get_account_entries(session, "P-CO-001", None, None)
    assert {row.entry_reference for row in entries} == {
        "E-CO-001",
        "E-CO-003",
        "E-CO-004",
    }
    native = cleaned_adapter.get_entry_detail(session, "E-CO-001")
    assert native.amount == 250000
    assert native.currency == "COP"
    assert native.country == "CO"
    assert native.credit_debit is None

    usd = cleaned_adapter.get_entry_detail(
        Session(customer_id="C-AR-001", expires_at="2026-07-02T00:00:00+00:00"),
        "E-AR-003",
    )
    assert usd.amount == 120
    assert usd.currency == "USD"
    assert usd.country == "AR"


def test_problem_transaction_reads_are_customer_scoped_and_status_only(cleaned_adapter):
    from calvino.tools.session import Session

    mexico = Session(customer_id="C-MX-001", expires_at="2026-07-02T00:00:00+00:00")
    argentina = Session(customer_id="C-AR-001", expires_at="2026-07-02T00:00:00+00:00")
    statuses = {
        entry.entry_reference: entry.status.value
        for entry in cleaned_adapter.list_problem_transactions(mexico, None, None)
    }

    assert set(statuses.values()) == {"Pending", "Declined", "Reversed"}
    assert "E-MX-001" not in statuses
    assert {
        row.entry_reference
        for row in cleaned_adapter.list_problem_transactions(argentina, None, None)
    } == {
        "E-AR-001",
        "E-AR-002",
    }
    assert all(
        "fraud" not in row.model_dump_json().lower()
        for row in cleaned_adapter.list_problem_transactions(argentina, None, None)
    )


def test_account_reads_only_return_rows_for_the_owned_product(cleaned_adapter):
    from calvino.tools.session import Session

    session = Session(customer_id="C-MX-001", expires_at="2026-07-02T00:00:00+00:00")
    entries = cleaned_adapter.get_account_entries(session, "P-MX-001", None, None)

    assert {entry.entry_reference for entry in entries} == {
        "E-MX-001",
        "E-MX-002",
        "E-MX-003",
        "E-MX-004",
        "E-MX-006",
        "E-MX-007",
        "E-MX-008",
    }
    assert all(entry.currency == "MXN" for entry in entries)


def test_reads_never_modify_source_files_or_write_source_rows_to_lineage(tmp_path):
    source = tmp_path / "cleaned-input"
    shutil.copytree(FIXTURE, source)
    before = {
        file.relative_to(source).as_posix(): file.read_bytes()
        for file in source.rglob("*")
        if file.is_file() and file.suffix == ".csv"
    }
    adapter = CleanedTableAdapter(source, lineage_path=tmp_path / "lineage.json")
    try:
        env = build_env(adapter)
        session = env.session("C-MX-001")
        env.tools.get_customer_summary(session)
        env.tools.list_accounts(session)
        token = env.token("C-MX-001", "request_cancellation", "E-MX-002")
        env.tools.request_cancellation(session, "E-MX-002", "immutable-source", token)
        after = {
            file.relative_to(source).as_posix(): file.read_bytes()
            for file in source.rglob("*")
            if file.is_file() and file.suffix == ".csv"
        }
        lineage = json.loads((tmp_path / "lineage.json").read_text(encoding="utf-8"))

        assert after == before
        assert set(lineage["tables"]) == {"customers", "products", "transactions"}
        assert all(len(info["sha256"]) == 64 for info in lineage["tables"].values())
        assert lineage["incomplete_source_counts"]["products.balance"] == 3
        assert lineage["incomplete_source_counts"]["products.status"] == 3
        assert lineage["incomplete_source_counts"]["customers.account_count"] == 3
        assert lineage["incomplete_source_counts"]["transactions.value_date"] == 14
        assert lineage["incomplete_source_counts"]["transactions.amount"] == 1
        serialized = json.dumps(lineage)
        assert "C-MX-001" not in serialized
        assert str(source) not in serialized
    finally:
        adapter.close()


def test_preflight_rejects_product_owned_by_a_different_customer(tmp_path):
    source = tmp_path / "bad-cleaned-layer"
    source.mkdir()
    for name in ("customers.csv", "products.csv", "transactions.csv"):
        shutil.copyfile(FIXTURE / name, source / name)
    products_path = source / "products.csv"
    contents = products_path.read_text(encoding="utf-8").replace(
        "P-MX-001,C-MX-001", "P-MX-001,C-CO-001"
    )
    products_path.write_text(contents, encoding="utf-8")

    with pytest.raises(ConfigurationError, match="ownership audit failed"):
        CleanedTableAdapter(source, lineage_path=tmp_path / "bad-lineage.json")


def test_lineage_output_refuses_to_overwrite_an_existing_file(tmp_path):
    target = tmp_path / "preserve.json"
    target.write_text("keep this file\n", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="already exists"):
        CleanedTableAdapter(FIXTURE, lineage_path=target)

    assert target.read_text(encoding="utf-8") == "keep this file\n"


def test_lineage_output_cannot_be_written_into_the_source_tree(tmp_path):
    source = tmp_path / "source"
    shutil.copytree(FIXTURE, source)
    target = source / "lineage.json"

    with pytest.raises(ConfigurationError, match="outside the source"):
        CleanedTableAdapter(source, lineage_path=target)

    assert not target.exists()


def test_unrepresentable_amount_is_returned_null_and_counted(tmp_path):
    source = tmp_path / "inexact-amount"
    shutil.copytree(FIXTURE, source)
    transaction_path = source / "transactions.csv"
    contents = transaction_path.read_text(encoding="utf-8").replace(
        "E-MX-002,C-MX-001,P-MX-001,2026-06-10,Transfer,Pending,5000,",
        "E-MX-002,C-MX-001,P-MX-001,2026-06-10,Transfer,Pending,5000.001,",
    )
    transaction_path.write_text(contents, encoding="utf-8")
    adapter = CleanedTableAdapter(source, lineage_path=tmp_path / "inexact-lineage.json")
    try:
        from calvino.tools.session import Session

        entry = adapter.get_entry_detail(
            Session(customer_id="C-MX-001", expires_at="2026-07-02T00:00:00+00:00"),
            "E-MX-002",
        )
        lineage = json.loads((tmp_path / "inexact-lineage.json").read_text(encoding="utf-8"))

        assert entry.amount is None
        assert lineage["incomplete_source_counts"]["transactions.amount_not_representable"] == 1
    finally:
        adapter.close()


def test_invalid_fraud_source_value_fails_preflight(tmp_path):
    source = tmp_path / "invalid-fraud"
    shutil.copytree(FIXTURE, source)
    transaction_path = source / "transactions.csv"
    contents = transaction_path.read_text(encoding="utf-8").replace(
        "E-CO-003,C-CO-001,P-CO-001,2026-06-18,Transfer,Pending,100000,COP,25.00,00,CO,false,App",
        "E-CO-003,C-CO-001,P-CO-001,2026-06-18,Transfer,Pending,100000,COP,25.00,00,CO,maybe,App",
    )
    transaction_path.write_text(contents, encoding="utf-8")

    with pytest.raises(ConfigurationError, match="fraud flags contain invalid"):
        CleanedTableAdapter(source, lineage_path=tmp_path / "invalid-fraud-lineage.json")


@pytest.mark.parametrize(
    ("entry_reference", "transaction_date", "status", "tool"),
    [
        ("E-MX-002", "2026-06-10", "Pending", "request_cancellation"),
        ("E-MX-003", "2026-06-12", "Declined", "retry_payment"),
    ],
)
def test_missing_transaction_type_refuses_writes_without_consuming_token(
    tmp_path, entry_reference, transaction_date, status, tool
):
    source = tmp_path / f"missing-type-{entry_reference}"
    shutil.copytree(FIXTURE, source)
    transaction_path = source / "transactions.csv"
    contents = transaction_path.read_text(encoding="utf-8").replace(
        f"{entry_reference},C-MX-001,P-MX-001,{transaction_date},Transfer,{status},",
        f"{entry_reference},C-MX-001,P-MX-001,{transaction_date},,{status},",
    )
    transaction_path.write_text(contents, encoding="utf-8")
    adapter = CleanedTableAdapter(source, lineage_path=tmp_path / f"lineage-{entry_reference}.json")
    try:
        env = build_env(adapter)
        session = env.session("C-MX-001")
        token = env.token("C-MX-001", tool, entry_reference)

        with pytest.raises(ToolRefusal) as caught:
            if tool == "request_cancellation":
                env.tools.request_cancellation(session, entry_reference, "missing-type", token)
            else:
                env.tools.retry_payment(session, entry_reference, "missing-type", token)

        assert caught.value.rule is Rule.SOURCE_INCOMPLETE
        assert adapter.action_log == []
        record = adapter.get_entry_record(session, entry_reference)
        env.verifier.verify_and_consume(
            token,
            customer_id="C-MX-001",
            action=tool,
            target_reference=entry_reference,
            amount=record.entry.amount,
            currency=record.entry.currency,
        )
    finally:
        adapter.close()


def test_missing_source_facts_fail_closed_through_bank_tools(cleaned_adapter):
    env = build_env(cleaned_adapter)
    session = env.session("C-CO-001")
    with pytest.raises(ToolRefusal) as caught:
        env.tools.request_cancellation(session, "E-CO-002", "incomplete-source", "not-a-token")

    assert caught.value.rule is Rule.SOURCE_INCOMPLETE
    assert env.adapter.action_log == []


def test_fraud_flagged_transaction_can_open_a_confirmed_investigation(cleaned_adapter):
    env = build_env(cleaned_adapter)
    session = env.session("C-AR-001")
    token = env.token("C-AR-001", "open_investigation", "E-AR-001")

    case = env.tools.open_investigation(
        session, "E-AR-001", "Customer disputes the transfer", "fraud-case", token
    )

    assert case.related_entry_reference == "E-AR-001"
    assert cleaned_adapter.action_log[-1]["action"] == "open_investigation"


def test_unknown_fraud_status_refuses_cancel_before_consuming_confirmation(cleaned_adapter):
    env = build_env(cleaned_adapter)
    session = env.session("C-CO-001")
    token = env.token("C-CO-001", "request_cancellation", "E-CO-004")

    with pytest.raises(ToolRefusal) as caught:
        env.tools.request_cancellation(session, "E-CO-004", "unknown-fraud", token)

    assert caught.value.rule is Rule.SOURCE_INCOMPLETE
    assert cleaned_adapter.action_log == []
    record = cleaned_adapter.get_entry_record(session, "E-CO-004")
    env.verifier.verify_and_consume(
        token,
        customer_id="C-CO-001",
        action="request_cancellation",
        target_reference="E-CO-004",
        amount=record.entry.amount,
        currency=record.entry.currency,
    )
