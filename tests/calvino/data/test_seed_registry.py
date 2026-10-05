"""Tests for the registry writer (TSD-019 P3, T-106).

Synthetic fixtures only: no network, GPU, keys, dataset, and no real
salt (a fixed non-secret string stands in).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from calvino.data import seed_registry as sr
from calvino.data.message_set import derive_seed_key, salted_customer_hash
from calvino.data.seed_pull import DrawnSeed, SeedCandidate

SALT = "test-salt-not-secret"
GATE = {"MXN": 8500.0, "COP": 2000000.0, "ARS": 175000.0, "USD": 500.0}


def drawn_tx(record_id="r-1", customer_id="C-1", kind="problem_transaction"):
    return DrawnSeed(
        candidate=SeedCandidate(
            record_id=record_id,
            customer_id=customer_id,
            event_date=date(2024, 3, 10),
            kind="problem_transaction" if kind == "other_customer" else kind,
            country_variant="MX",
            status="Pending",
            transaction_type="transfer",
            amount=4000.0,
            currency="MXN",
            channel="app",
        ),
        split="train",
        kind=kind,
    )


def drawn_complaint():
    return DrawnSeed(
        candidate=SeedCandidate(
            record_id="c-1",
            customer_id="C-9",
            event_date=date(2024, 5, 1),
            kind="complaint",
            country_variant="CO",
            complaint_status="open",
            sla_state="within_sla",
        ),
        split="train",
        kind="complaint",
    )


def test_rows_carry_facts_only_with_recomputable_keys():
    """Keys and hashes recompute from the pointers; raw ids appear nowhere."""
    seeds, pointers = sr.build_registry(
        [drawn_tx(), drawn_complaint()], salt=SALT, policy_version="v2", gate_limits=GATE
    )
    assert len(seeds) == len(pointers) == 2
    for seed, pointer in zip(seeds, pointers, strict=True):
        assert seed.seed_key == derive_seed_key(
            salt=SALT,
            set_version="v1",
            split="train",
            kind=seed.kind,
            record_id=pointer.record_id,
        )
        assert seed.customer_hash == salted_customer_hash(pointer.customer_id, SALT)
        assert pointer.salt_version == "salt-v1"
        dumped = seed.model_dump_json()
        assert pointer.record_id not in dumped
        assert pointer.customer_id not in dumped
        assert SALT not in dumped
    assert seeds[0].record_facts.amount_band == "under_gate"
    assert seeds[0].gate_limit_used == 8500.0
    assert seeds[0].policy_version == "v2"
    assert seeds[1].record_facts.complaint_status == "open"


def test_nominal_batch_fills_only_its_quota_cell():
    """Nominal batches are variant-spread, deterministic, and never backfill."""
    assert sr.NO_RECORD_BACKFILLS_SHORTFALLS is False
    seeds, pointers = sr.build_nominal_seeds("train", 6, salt=SALT, policy_version="v2")
    assert len(seeds) == len(pointers) == 6
    assert all(seed.kind == "no_record" for seed in seeds)
    assert sorted(seed.country_variant for seed in seeds) == ["AR"] * 2 + ["CO"] * 2 + ["MX"] * 2
    assert all(seed.record_facts.amount_band is None for seed in seeds)
    assert len({seed.seed_key for seed in seeds}) == 6
    repeat, _ = sr.build_nominal_seeds("train", 6, salt=SALT, policy_version="v2")
    assert [s.seed_key for s in repeat] == [s.seed_key for s in seeds]


def test_nominal_no_record_seed_hashes_its_persona():
    """No-record rows hash the nominal persona id and carry no band."""
    seed, pointer = sr.nominal_seed(
        persona_id="persona-mx-01",
        country_variant="MX",
        event_date="2026-03-01",
        salt=SALT,
        policy_version="v2",
    )
    assert seed.kind == "no_record"
    assert seed.record_facts.amount_band is None
    assert seed.customer_hash == salted_customer_hash("persona-mx-01", SALT)
    assert "persona-mx-01" not in seed.model_dump_json()
    assert pointer.record_id == "persona-mx-01"


def test_pointer_log_refuses_a_committable_path(tmp_path, monkeypatch):
    """A pointer log git would commit is refused, never written."""
    monkeypatch.setattr(sr, "is_git_ignored", lambda path: False)
    candidate = tmp_path / "seed-log.jsonl"
    with pytest.raises(SystemExit, match="not git-ignored"):
        sr.write_pointer_log(candidate, [])
    assert not candidate.exists()


def test_pointer_log_round_trip_and_registry_reload(tmp_path, monkeypatch):
    """Pointers persist git-ignored; registry rows reload as valid seeds."""
    monkeypatch.setattr(sr, "is_git_ignored", lambda path: True)
    seeds, pointers = sr.build_registry(
        [drawn_tx()], salt=SALT, policy_version="v2", gate_limits=GATE
    )
    registry = tmp_path / "seeds.train.jsonl"
    log = tmp_path / "seed-log.jsonl"
    assert sr.write_seeds_jsonl(registry, seeds) == 1
    assert sr.write_pointer_log(log, pointers) == 1
    assert SALT not in registry.read_text(encoding="utf-8")
    reloaded = sr.load_seed_registry(registry)
    assert [s.seed_key for s in reloaded] == [s.seed_key for s in seeds]
    mapping = sr.record_ids_from_pointer_log(log)
    assert mapping[seeds[0].seed_key] == "r-1"
    log_text = log.read_text(encoding="utf-8")
    assert json.loads(log_text)["salt_version"] == "salt-v1"


def test_ensure_salt_refuses_committable_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sr, "is_git_ignored", lambda path: False)
    with pytest.raises(SystemExit, match="not git-ignored"):
        sr.ensure_salt(tmp_path / "salt")


def test_ensure_salt_creates_once_and_reloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sr, "is_git_ignored", lambda path: True)
    first = sr.ensure_salt(tmp_path / "salt-v1")
    assert len(first) == 64
    assert (tmp_path / "salt-v1").stat().st_mode & 0o077 == 0
    assert sr.ensure_salt(tmp_path / "salt-v1") == first
