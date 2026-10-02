"""Row models and rule registry (TSD-007): valid rows pass, malformed rows name the field."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from calvino.data import RULES, TABLES, Severity, rules_for, validate_records
from calvino.data.schemas import build_schema_files

TX = {
    "transaction_id": "T1",
    "customer_id": "C1",
    "transaction_status": "Pending",
    "currency": "MXN",
    "amount": 3200.0,
}


def test_every_table_has_a_primary_key_in_its_required_columns():
    for contract in TABLES.values():
        assert set(contract.primary_key) <= set(contract.required), contract.name


def test_every_rule_targets_a_known_table_and_ids_are_unique():
    assert {r.table for r in RULES} <= set(TABLES)
    ids = [r.rule_id for r in RULES]
    assert len(ids) == len(set(ids))


def test_foreign_keys_point_to_known_tables():
    for contract in TABLES.values():
        for fk in contract.foreign_keys:
            assert fk.parent in TABLES, (contract.name, fk.parent)


def test_known_defects_from_data_md_are_never_errors():
    known = {
        "TX-RESPONSE-CODE-NULL",
        "TX-COUNTRY-MEXICO",
        "CP-AMOUNT-NO-CURRENCY",
        "CP-ORIGIN-NULL",
        "CI-REASON-REPEATS",
    }
    for rule in RULES:
        if rule.rule_id in known:
            assert rule.severity is Severity.KNOWN_DEFECT, rule.rule_id
    branch_fk = TABLES["service_agents"].foreign_keys[0]
    assert branch_fk.severity is Severity.KNOWN_DEFECT


def test_rules_for_filters_by_table():
    assert {r.rule_id for r in rules_for("complaints")} == {
        "CP-AMOUNT-NO-CURRENCY",
        "CP-ORIGIN-NULL",
    }


def test_valid_transaction_with_null_response_code_passes():
    result = validate_records("transactions", [{**TX, "response_code": None}])
    assert (result.valid, result.invalid) == (1, 0)


@pytest.mark.parametrize(
    ("change", "field"),
    [
        ({"transaction_status": "Settled"}, "transaction_status"),
        ({"currency": "BRL"}, "currency"),
        ({"transaction_id": ""}, "transaction_id"),
    ],
)
def test_malformed_transaction_names_the_field(change, field):
    result = validate_records("transactions", [{**TX, **change}])
    assert result.invalid == 1
    assert any(key.startswith(field) for key in result.errors)


def test_missing_required_column_is_reported():
    row = {k: v for k, v in TX.items() if k != "transaction_status"}
    result = validate_records("transactions", [row])
    assert any(key.startswith("transaction_status") for key in result.errors)


def test_customer_outside_the_three_countries_is_rejected():
    result = validate_records("customers", [{"customer_id": "C9", "country": "Brasil"}])
    assert result.invalid == 1


def test_nan_is_read_as_missing():
    result = validate_records("transactions", [{**TX, "amount": math.nan}])
    assert result.valid == 1


def test_exchange_rate_must_be_positive():
    row = {"date": "2023-06-17", "source_currency": "MXN", "target_currency": "USD"}
    assert validate_records("daily_exchange_rates", [{**row, "exchange_rate": 0.058}]).valid == 1
    assert validate_records("daily_exchange_rates", [{**row, "exchange_rate": 0}]).invalid == 1


def test_unnamed_columns_are_ignored():
    result = validate_records("customers", [{"customer_id": "C1", "country": "México", "x": 1}])
    assert result.valid == 1


def test_exported_schemas_are_up_to_date():
    out = Path(__file__).resolve().parents[3] / "contracts" / "data"
    for name, content in build_schema_files().items():
        assert (out / name).read_text(encoding="utf-8") == content, (
            f"{name} is stale: run uv run python scripts/export_data_schemas.py"
        )


def test_schema_carries_keys_and_rules():
    schema = json.loads(build_schema_files()["complaints.schema.json"])
    extra = schema["x-calvino"]
    assert extra["primary_key"] == ["complaint_id"]
    assert {r["id"] for r in extra["rules"]} == {"CP-AMOUNT-NO-CURRENCY", "CP-ORIGIN-NULL"}


def test_lineage_names_scripts_that_exist():
    root = Path(__file__).resolve().parents[3]
    lineage = json.loads((root / "contracts" / "data" / "lineage.json").read_text("utf-8"))
    for step in lineage["steps"]:
        script = step.get("script", "")
        if script.startswith("scripts/"):
            assert (root / script).is_file(), script
