"""Synthetic streaming inventory tests; no real dataset or network."""

from __future__ import annotations

import io

import pytest

from calvino.data.inventory_access import TABLE_NAMES, InventoryError, SourceObject
from calvino.data.inventory_scan import scan_table


def test_full_table_catalog_is_counted_without_raw_values() -> None:
    objects = {
        name: SourceObject(name, f"data/{name}.csv", 20, "synthetic", None) for name in TABLE_NAMES
    }
    rows = {
        "customers": b"\xef\xbb\xbfcustomer_id,country,segment\nprivate-id,M\xc3\xa9xico,Basic\n",
        "products": b"product_id,customer_id,currency\nproduct-a,private-id,USD\n",
        "branches": b"branch_id\nbranch-a\n",
        "service_agents": b"agent_id,assigned_branch_id\nagent-a,branch-a\n",
        "transactions": (
            b"transaction_id,customer_id,transaction_status,transaction_type,currency,"
            b"response_code,transaction_country\nprivate-id,private-id,Pending,Transfer,MXN,,Mexico\n"
        ),
        "call_center_interactions": (
            b"interaction_id,customer_id,reason_category,contact_reason\n"
            b"private-id,private-id,Transaccional,Transaccional\n"
        ),
        "complaints": (
            b"complaint_id,customer_id,category,status,claimed_amount,currency,"
            b"origin_interaction_id\nprivate-id,private-id,Transactions,Open,10,USD,\n"
        ),
        "daily_exchange_rates": (
            b"date,source_currency,target_currency,exchange_rate\n2026-10-03,MXN,USD,0.05\n"
        ),
    }
    for name, obj in objects.items():
        source = rows.get(name, b"id,value\nprivate-id,not-public\n")
        result = scan_table(name, [obj], lambda _, data=source: io.BytesIO(data)).result()
        assert result["rows"] == 1
        assert "private-id" not in str(result)
    assert len(objects) == 13


def test_missing_empty_type_counts_and_schema_drift() -> None:
    objects = [
        SourceObject("customers", "first", 20, "synthetic", None),
        SourceObject("customers", "second", 20, "synthetic", None),
    ]
    data = {
        "first": b"customer_id,country,segment\none,Argentina,\n",
        "second": b"customer_id,country,other\nsecond,Colombia,7\n",
    }
    result = scan_table("customers", objects, lambda obj: io.BytesIO(data[obj.key])).result()
    assert result["rows"] == 2
    assert result["columns"]["segment"]["empty"] == 1
    assert result["columns"]["segment"]["missing"] == 1
    assert result["columns"]["other"]["missing"] == 1
    assert result["columns"]["other"]["types"] == {"integer": 1}
    assert result["schema_drift"] == {
        "files_with_extra_columns": 1,
        "files_with_missing_columns": 1,
    }


def test_unknown_category_value_is_not_exposed() -> None:
    obj = SourceObject("customers", "synthetic", 15, "synthetic", None)
    result = scan_table(
        "customers",
        [obj],
        lambda _: io.BytesIO(b"customer_id,country\nprivate-id,not-an-approved-country\n"),
    ).result()
    assert result["categories"]["country"]["counts"] == {"(other)": 1}
    assert "not-an-approved-country" not in str(result)
    assert result["categories"]["country"]["small_n"] == ["(other)"]


def test_type_drift_is_counted_without_examples() -> None:
    objects = [
        SourceObject("digital_events", "first", 12, "synthetic", None),
        SourceObject("digital_events", "second", 12, "synthetic", None),
    ]
    rows = {"first": b"id,value\none,42\n", "second": b"id,value\ntwo,private-text\n"}
    result = scan_table("digital_events", objects, lambda obj: io.BytesIO(rows[obj.key])).result()
    assert result["schema_drift"]["files_with_incompatible_type_families"] == 1
    assert "private-text" not in str(result)


def test_numeric_formats_and_empty_partition_are_not_schema_drift() -> None:
    objects = [
        SourceObject("digital_events", "first", 12, "synthetic", None),
        SourceObject("digital_events", "second", 12, "synthetic", None),
        SourceObject("digital_events", "third", 12, "synthetic", None),
    ]
    rows = {
        "first": b"id,value\none,42\n",
        "second": b"id,value\ntwo,3.5e-05\n",
        "third": b"id,value\n",
    }
    result = scan_table("digital_events", objects, lambda obj: io.BytesIO(rows[obj.key])).result()
    assert result["schema_drift"] == {}
    assert result["columns"]["value"]["types"] == {"decimal": 1, "integer": 1}


def test_type_baseline_starts_at_first_nonempty_partition() -> None:
    objects = [
        SourceObject("digital_events", name, 12, "synthetic", None)
        for name in ("empty", "numeric", "text")
    ]
    rows = {
        "empty": b"id,value\none,\n",
        "numeric": b"id,value\ntwo,42\n",
        "text": b"id,value\nthree,private-text\n",
    }
    result = scan_table("digital_events", objects, lambda obj: io.BytesIO(rows[obj.key])).result()
    assert result["schema_drift"]["files_with_incompatible_type_families"] == 1


def test_empty_contact_reasons_do_not_count_as_repeated() -> None:
    obj = SourceObject("call_center_interactions", "synthetic", 20, "synthetic", None)
    row = b"interaction_id,customer_id,reason_category,contact_reason\none,customer-a,,\n"
    result = scan_table("call_center_interactions", [obj], lambda _: io.BytesIO(row)).result()
    assert result["row_rule_violations"].get("CI-REASON-REPEATS", 0) == 0


def test_invalid_csv_row_fails_without_echoing_value() -> None:
    obj = SourceObject("customers", "synthetic", 15, "synthetic", None)
    with pytest.raises(InventoryError, match="unexpected CSV field") as error:
        scan_table(
            "customers",
            [obj],
            lambda _: io.BytesIO(b"customer_id,country\none,Argentina,private-value\n"),
        )
    assert "private-value" not in str(error.value)


def test_missing_contract_column_fails_before_aggregation() -> None:
    obj = SourceObject("transactions", "synthetic", 10, "synthetic", None)
    with pytest.raises(InventoryError, match="missing required inventory columns"):
        scan_table("transactions", [obj], lambda _: io.BytesIO(b"transaction_id\none\n"))
