"""Row models and rule registry (TSD-007): valid rows pass, malformed rows name the field."""

from __future__ import annotations

from calvino.data import RULES, TABLES, Severity, rules_for


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
