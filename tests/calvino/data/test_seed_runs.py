"""Tests for the oracle-bridge run and the registry check entrypoint (T-106).

Synthetic fixtures only: no network, GPU, keys, dataset or salt. The
bridge test is the regression for audit fix #1: brief-derived defaults
must fire on unreviewed rows, so the oracle is defined on every row.
"""

from __future__ import annotations

from datetime import date

import pytest

from calvino.data import message_set as ms
from calvino.data import seed_registry as sr
from calvino.data.seed_pull import DrawnSeed, SeedCandidate

SALT = "test-salt-not-secret"
GATE = {"MXN": 8500.0, "COP": 2000000.0, "ARS": 175000.0, "USD": 500.0}

BASE_ROW = {
    "split": "train",
    "prompt_id": "train-v1",
    "customer_hash": "a" * 16,
    "country_variant": "MX",
    "event_date": "2024-03-10",
    "policy_version": "v2",
    "gate_table_hash": ms.gate_table_hash(GATE),
}


def seed_row(seed_key, kind, facts, **overrides):
    row = {
        **BASE_ROW,
        "seed_key": seed_key,
        "kind": kind,
        "record_facts": {"kind": kind, **facts},
    }
    if "amount_band" not in row["record_facts"]:
        row = {**row, "gate_table_hash": None}
    row.update(overrides)
    return sr.SeedRow.model_validate(row)


def registry():
    return [
        seed_row(
            "v1-tx",
            "problem_transaction",
            {"status": "Pending", "currency": "MXN", "amount_band": "under_gate"},
        ),
        seed_row(
            "v1-clean",
            "clean_transaction",
            {"status": "Approved", "currency": "MXN", "amount_band": "under_gate"},
        ),
        seed_row(
            "v1-other",
            "other_customer",
            {"status": "Pending", "currency": "MXN", "amount_band": "under_gate"},
        ),
        seed_row(
            "v1-case",
            "complaint",
            {"complaint_status": "open", "sla_state": "within_sla"},
            country_variant="CO",
            event_date="2024-05-01",
        ),
        seed_row("v1-none", "no_record", {}),
        seed_row(
            "v1-hand",
            "hand_written",
            {"status": "Declined", "currency": "MXN", "amount_band": "over_gate"},
        ),
    ]


def briefs():
    return {
        "v1-tx": {"intent": "explain"},
        "v1-clean": {"intent": "cancel"},
        "v1-other": {"intent": "explain"},
        "v1-case": {"intent": "open_case"},
        "v1-none": {"intent": "out_of_scope"},
        "v1-hand": {"intent": "retry"},
    }


def test_bridge_defines_the_oracle_on_every_unreviewed_row():
    """Defaults fire without review: each row bridges to a named outcome."""
    bridged = sr.bridge_registry_to_oracle(registry(), briefs(), gate_limits=GATE)
    assert len(bridged) == 6
    assert all(b.reviewed is False for b in bridged)
    by_key = {b.seed_key: b for b in bridged}
    assert by_key["v1-tx"].outcome == "explain"
    assert by_key["v1-other"].outcome == "refuse_access"
    assert by_key["v1-case"].outcome == "investigate"
    assert by_key["v1-none"].outcome == "out_of_scope"
    assert by_key["v1-hand"].outcome == "act_ask"
    assert by_key["v1-tx"].labels.clear_enough is True


def test_bridge_dispute_defaults_need_a_person():
    """A dispute brief defaults to needs-person through the full bridge."""
    seeds = [
        seed_row(
            "v1-d",
            "problem_transaction",
            {"status": "Declined", "currency": "MXN", "amount_band": "under_gate"},
        )
    ]
    (row,) = sr.bridge_registry_to_oracle(seeds, {"v1-d": {"intent": "dispute"}}, gate_limits=GATE)
    assert row.labels.needs_person is True


def test_bridge_reviewed_correction_overrides_the_default():
    """A reviewed row carries its logged correction, not the default."""
    seeds = [
        seed_row(
            "v1-r",
            "problem_transaction",
            {"status": "Pending", "currency": "MXN", "amount_band": "under_gate"},
        )
    ]
    (row,) = sr.bridge_registry_to_oracle(
        seeds,
        {
            "v1-r": {
                "intent": "explain",
                "reviewed": True,
                "labels": {
                    "workflow_area": "stuck payment",
                    "stuck_intent": "status",
                    "clear_enough": False,
                    "needs_person": False,
                    "injection": False,
                },
                "oracle_facts": {
                    "intent": "explain",
                    "ambiguous": True,
                    "in_scope": True,
                },
            }
        },
        gate_limits=GATE,
    )
    assert row.reviewed is True
    assert row.labels.clear_enough is False
    assert row.oracle_facts.ambiguous is True
    assert row.outcome == "clarify"


def test_bridge_rejects_unset_area_for_reviewed_non_none_intent():
    seeds = [
        seed_row(
            "v1-r",
            "problem_transaction",
            {"status": "Pending", "currency": "MXN", "amount_band": "under_gate"},
        )
    ]
    with pytest.raises(ValueError, match="only for oracle intent 'none'"):
        sr.bridge_registry_to_oracle(
            seeds,
            {
                "v1-r": {
                    "intent": "explain",
                    "reviewed": True,
                    "labels": {
                        "workflow_area": None,
                        "stuck_intent": None,
                        "clear_enough": False,
                        "needs_person": False,
                        "injection": False,
                    },
                    "oracle_facts": {
                        "intent": "explain",
                        "ambiguous": True,
                        "in_scope": True,
                    },
                }
            },
            gate_limits=GATE,
        )


def test_bridge_missing_brief_fails_loudly():
    """A row with no brief raises instead of deriving a silent default."""
    try:
        sr.bridge_registry_to_oracle(registry(), {}, gate_limits=GATE)
    except KeyError as error:
        assert "no brief" in str(error)
    else:
        raise AssertionError("a missing brief must fail loudly")


def write_registry(tmp_path):
    seeds, _ = sr.build_registry(
        [
            DrawnSeed(
                candidate=SeedCandidate(
                    record_id="r-1",
                    customer_id="C-1",
                    event_date=date(2024, 3, 10),
                    kind="problem_transaction",
                    country_variant="MX",
                    status="Pending",
                    amount=4000.0,
                    currency="MXN",
                ),
                split="train",
                kind="problem_transaction",
            )
        ],
        salt=SALT,
        policy_version="v2",
        gate_limits=GATE,
    )
    first = tmp_path / "seeds.train.jsonl"
    sr.write_seeds_jsonl(first, seeds)
    return first, seeds


def test_entrypoint_green_on_clean_files(tmp_path):
    """The file entrypoint loads registries by id and passes clean inputs."""
    first, seeds = write_registry(tmp_path)
    report = sr.run_checks_from_files({"train": first})
    assert report.passed, [v.detail for v in report.violations]
    assert any("pointer log" in note for note in report.notes)
    assert seeds[0].seed_key.startswith("v1-")


def test_entrypoint_fires_l1_across_split_files(tmp_path):
    """One customer hash in two split files fails L1 through the entrypoint."""
    first, _ = write_registry(tmp_path)
    twin = sr.SeedRow.model_validate(
        {
            **BASE_ROW,
            "seed_key": "v1-other-split",
            "split": "test",
            "prompt_id": "test-v1",
            "kind": "problem_transaction",
            "customer_hash": sr.salted_customer_hash("C-1", SALT),
            "record_facts": {"kind": "problem_transaction", "status": "Pending"},
            "event_date": "2026-02-10",
            "gate_table_hash": None,
        }
    )
    second = tmp_path / "seeds.test.jsonl"
    sr.write_seeds_jsonl(second, [twin])
    report = sr.run_checks_from_files({"train": first, "test": second})
    assert any(v.rule_id == "L1" for v in report.violations)
