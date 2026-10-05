"""Tests for the message-set module (TSD-019, T-106).

Synthetic fixtures only: no network, GPU, keys, dataset or salt.
"""

import pytest
from pydantic import ValidationError

from calvino.data import message_set as ms
from calvino.data.message_set import MessageProvenance, MessageRow, SeedRow

SALT = "test-salt-not-secret"
GATE = {"MXN": 8500.0, "COP": 2000000.0, "ARS": 175000.0, "USD": 500.0}
HARD = {"MXN": 85000.0, "COP": 20000000.0, "ARS": 1750000.0, "USD": 5000.0}


def make_seed(**overrides) -> SeedRow:
    """One synthetic train seed with usable defaults."""
    base = {
        "seed_key": "v1-abc123def456",
        "split": "train",
        "prompt_id": "train-v1",
        "kind": "problem_transaction",
        "customer_hash": "0123456789abcdef",
        "country_variant": "MX",
        "record_facts": {
            "kind": "problem_transaction",
            "status": "Pending",
            "amount": 4500.0,
            "amount_band": "under_gate",
            "currency": "MXN",
        },
        "event_date": "2024-03-10",
        "policy_version": "v2",
        "gate_limit_used": 8500.0,
    }
    base.update(overrides)
    return SeedRow.model_validate(base)


def make_message(**overrides) -> MessageRow:
    """One synthetic train message with usable defaults."""
    base = {
        "msg_id": "train-0001",
        "split": "train",
        "language_variant": "es-MX",
        "message": "¿Dónde está mi transferencia de 4,500 MXN?",
        "seed_key": "v1-abc123def456",
        "labels": {
            "workflow_area": "stuck payment",
            "stuck_intent": "status",
            "clear_enough": True,
            "needs_person": False,
            "injection": False,
        },
        "oracle_facts": {
            "intent": "explain",
            "ambiguous": False,
            "status": "Pending",
            "owner": True,
            "amount_band": "under_gate",
            "fraud_flag": False,
            "in_scope": True,
        },
        "provenance": {
            "prompt_id": "train-v1",
            "prompt_version": "v1",
            "model_id": "Qwen/Qwen3.6-35B-A3B-FP8",
            "review_verdict": "unreviewed",
        },
        "synthetic": True,
    }
    base.update(overrides)
    return MessageRow.model_validate(base)


# Seed keys.


def test_seed_key_deterministic_and_prefixed():
    """The same inputs always give the same version-prefixed key."""
    first = ms.derive_seed_key(
        salt=SALT,
        set_version="v1",
        split="train",
        kind="problem_transaction",
        record_id="rec-1",
    )
    second = ms.derive_seed_key(
        salt=SALT,
        set_version="v1",
        split="train",
        kind="problem_transaction",
        record_id="rec-1",
    )
    assert first == second
    assert first.startswith("v1-")
    assert len(first) == 15


def test_seed_key_opaque_and_unique():
    """Keys reveal no record, customer or date, and differ per input."""
    key = ms.derive_seed_key(
        salt=SALT,
        set_version="v1",
        split="train",
        kind="problem_transaction",
        record_id="C-123",
    )
    assert "C-123" not in key
    assert "train" not in key.replace("v1-", "")
    other = ms.derive_seed_key(
        salt=SALT,
        set_version="v1",
        split="train",
        kind="problem_transaction",
        record_id="C-124",
    )
    assert key != other
    rewording = ms.derive_seed_key(
        salt=SALT,
        set_version="v1",
        split="test",
        kind="rewording",
        record_id="C-123",
        role="rewording-1",
    )
    assert rewording != key


def test_customer_hash_truncated_and_salted():
    """Sixteen hex chars that move with the salt."""
    hashed = ms.salted_customer_hash("C-123", SALT)
    assert len(hashed) == 16
    assert hashed != ms.salted_customer_hash("C-123", "other-salt")
    assert "C-123" not in hashed


def test_duplicate_draw_fails_on_redrawn_record():
    """Drawing one record id twice in one split fails loudly."""
    seeds = [make_seed(seed_key="v1-aaa"), make_seed(seed_key="v1-bbb")]
    assert ms.check_duplicate_draw(seeds, ["rec-1", "rec-1"])
    assert ms.check_duplicate_draw(seeds, ["rec-1", "rec-2"]) == []
    assert ms.check_duplicate_draw(seeds, [None, None]) == []


def test_duplicate_seed_key_fails():
    """No seed key twice in one registry."""
    seeds = [make_seed(seed_key="v1-same"), make_seed(seed_key="v1-same")]
    assert ms.check_duplicate_draw(seeds, ["rec-1", "rec-2"])


# Brief-derived defaults, branch by branch.


def test_defaults_stuck_status_row():
    """A plain status brief defaults to a clear, in-scope explanation."""
    labels, facts = ms.derive_defaults(
        brief_intent="explain", adversarial_kind=None, seed_kind="problem_transaction"
    )
    assert (labels.workflow_area, labels.stuck_intent) == ("stuck payment", "status")
    assert labels.clear_enough is True
    assert labels.needs_person is False
    assert labels.injection is False
    assert (facts.intent, facts.ambiguous, facts.in_scope) == ("explain", False, True)


def test_defaults_dispute_needs_person():
    """Dispute and fraud-report heads default to needs-person."""
    for intent in ("dispute", "fraud_report"):
        labels, facts = ms.derive_defaults(
            brief_intent=intent, adversarial_kind=None, seed_kind="problem_transaction"
        )
        assert labels.needs_person is True
        assert facts.intent == "explain"
        assert facts.in_scope is True


def test_defaults_manipulation_is_injection_not_needs_person():
    """Injection is labelled separately; the oracle still queues a human."""
    labels, facts = ms.derive_defaults(
        brief_intent="manipulation", adversarial_kind=None, seed_kind="problem_transaction"
    )
    assert labels.injection is True
    assert labels.needs_person is False
    assert facts.intent == "manipulation"
    assert ms.expected_outcome(make_seed(), labels, facts) == "human_queue"


def test_defaults_explicit_human_request_needs_person():
    labels, facts = ms.derive_defaults(
        brief_intent="human", adversarial_kind=None, seed_kind="problem_transaction"
    )
    assert labels.needs_person is True
    assert facts.intent == "human"
    assert ms.expected_outcome(make_seed(), labels, facts) == "human_queue"


def test_injection_carrier_does_not_default_to_needs_person():
    """An adversarial-kind label alone does not assert an explicit handoff."""
    labels, _ = ms.derive_defaults(
        brief_intent="explain", adversarial_kind="injection", seed_kind="problem_transaction"
    )
    assert labels.injection is True
    assert labels.needs_person is False


def test_defaults_empty_garbled_unclear():
    """Empty/garbled is ambiguous in-scope and the oracle clarifies."""
    labels, facts = ms.derive_defaults(
        brief_intent="none", adversarial_kind=None, seed_kind="no_record"
    )
    assert labels.clear_enough is False
    assert labels.workflow_area is None
    assert facts.intent == "none"
    assert facts.ambiguous is True
    assert facts.in_scope is True
    assert ms.expected_outcome(make_seed(kind="no_record"), labels, facts) == "clarify"

    for kind in ("wrong_data", "missing_data", "multilingual"):
        probing_labels, probing_facts = ms.derive_defaults(
            brief_intent="explain", adversarial_kind=kind, seed_kind="problem_transaction"
        )
        assert probing_labels.clear_enough is False
        assert probing_facts.ambiguous is True


def test_no_record_seed_does_not_override_brief_scope():
    """The brief distinguishes ambiguous in-scope from explicit out-of-scope."""
    _, facts = ms.derive_defaults(
        brief_intent="out_of_scope", adversarial_kind=None, seed_kind="no_record"
    )
    assert facts.in_scope is False
    _, ambiguous_facts = ms.derive_defaults(
        brief_intent="none", adversarial_kind=None, seed_kind="no_record"
    )
    assert ambiguous_facts.in_scope is True
    _, stuck_facts = ms.derive_defaults(
        brief_intent="cancel", adversarial_kind=None, seed_kind="no_record"
    )
    assert stuck_facts.in_scope is True


# The record-facts to OracleFacts bridge.


def test_hand_written_status_passes_through():
    """Hand-written rows carry nominal transaction status into the oracle;
    only no-record and complaint seeds read None."""
    seed = make_seed(kind="hand_written")
    labels, facts = ms.derive_defaults(
        brief_intent="cancel", adversarial_kind=None, seed_kind="hand_written"
    )
    oracle = ms.seed_to_oracle_facts(seed, labels, facts, gate_limits=GATE)
    assert oracle.status == "Pending"


def test_other_customer_maps_to_refuse_access():
    """An other-customer seed reads owner false: the oracle refuses access."""
    seed = make_seed(kind="other_customer")
    labels, facts = ms.derive_defaults(
        brief_intent="explain", adversarial_kind=None, seed_kind="other_customer"
    )
    oracle = ms.seed_to_oracle_facts(seed, labels, facts, gate_limits=GATE)
    assert oracle.owner is False
    assert ms.expected_outcome(seed, labels, facts) == "refuse_access"


def test_complaint_seed_maps_to_none_status():
    """Complaint seeds carry no transaction status into the oracle."""
    seed = make_seed(
        kind="complaint",
        record_facts={"kind": "complaint", "complaint_status": "open", "sla_state": "within_sla"},
    )
    labels, facts = ms.derive_defaults(
        brief_intent="open_case", adversarial_kind=None, seed_kind="complaint"
    )
    oracle = ms.seed_to_oracle_facts(seed, labels, facts, gate_limits=GATE)
    assert oracle.status is None
    assert ms.expected_outcome(seed, labels, facts) == "investigate"


def test_over_gate_write_parks_for_a_person():
    """An over-gate retry derives act_ask through the shared oracle."""
    seed = make_seed(
        record_facts={
            "kind": "problem_transaction",
            "status": "Declined",
            "amount": 12000.0,
            "amount_band": "over_gate",
            "currency": "MXN",
        },
        gate_limit_used=8500.0,
    )
    labels, facts = ms.derive_defaults(
        brief_intent="retry", adversarial_kind=None, seed_kind="problem_transaction"
    )
    assert ms.expected_outcome(seed, labels, facts) == "act_ask"


def test_oracle_defined_on_unreviewed_rows():
    """Every brief intent derives a usable oracle input with no review."""
    for intent in (
        "explain",
        "cancel",
        "retry",
        "open_case",
        "case_status",
        "human",
        "manipulation",
        "none",
        "dispute",
        "fraud_report",
        "out_of_scope",
    ):
        labels, facts = ms.derive_defaults(
            brief_intent=intent, adversarial_kind=None, seed_kind="problem_transaction"
        )
        seed = make_seed()
        ms.seed_to_oracle_facts(seed, labels, facts, gate_limits=GATE)


def test_policy_guard_raises_on_oracle_path_only():
    """A re-banded policy raises on the oracle path, never on text reads."""
    seed = make_seed(gate_limit_used=9000.0)
    labels, facts = ms.derive_defaults(
        brief_intent="explain", adversarial_kind=None, seed_kind="problem_transaction"
    )
    with pytest.raises(ValueError, match="mint a new set version"):
        ms.seed_to_oracle_facts(seed, labels, facts, gate_limits=GATE)
    ms.seed_to_oracle_facts(seed, labels, facts, text_only=True)


def test_amount_margins():
    """Seeds avoid ±20% of the gate line and the hard-rule line."""
    assert ms.usable_amount(4000.0, "MXN", GATE, HARD) is True
    assert ms.usable_amount(8000.0, "MXN", GATE, HARD) is False
    assert ms.usable_amount(9000.0, "MXN", GATE, HARD) is False
    assert ms.usable_amount(15000.0, "MXN", GATE, HARD) is True
    assert ms.usable_amount(70000.0, "MXN", GATE, HARD) is False
    assert ms.usable_amount(90000.0, "MXN", GATE, HARD) is False
    assert ms.amount_band_for(4500.0, "MXN", GATE) == "under_gate"
    assert ms.amount_band_for(12000.0, "MXN", GATE) == "over_gate"


# Normalisation and near duplicates.


def test_normalize_text_pins_behaviour():
    """Diacritics survive; case/punctuation/emoji/spacing collapse."""
    assert ms.normalize_text("  ¿Dónde ESTÁ mi pago?! ") == "dónde está mi pago"
    assert ms.normalize_text("dónde") != "donde"
    assert ms.normalize_text("Hola   mundo") == "hola mundo"
    assert "😀" not in ms.normalize_text("hola 😀 mundo")
    assert ms.normalize_text("pago...¿qué pasó?") == "pago qué pasó"


def test_jaccard_threshold():
    """Identical sets score 1.0; disjoint sets score 0.0."""
    assert ms.jaccard("hola mundo", "hola mundo") == 1.0
    assert ms.jaccard("hola mundo", "adiós pago") == 0.0
    assert ms.jaccard("", "") == 0.0


def test_exact_match_is_duplicate():
    """Post-normalisation equality fails however it is punctuated."""
    assert ms.is_near_duplicate("¿Dónde está mi pago?", "Dónde está mi pago!!  ") is True
    assert ms.is_near_duplicate("¿Dónde está mi pago?", "donde esta mi pago") is False


def test_empty_normalisation_falls_back_to_raw():
    """Emoji-only rows compare raw: identical raws collide, distinct do not."""
    assert ms.is_near_duplicate("😀", "😀") is True
    assert ms.is_near_duplicate("😀", "🎉") is False
    assert ms.is_near_duplicate("", "") is True


def test_rewording_noop_fails():
    """A rewording identical to its parent is a no-op and fails."""
    assert ms.messages_differ("¿Dónde está mi pago?", "¿dónde está mi pago?!") is False
    assert ms.messages_differ("¿Dónde está mi pago?", "Quiero saber dónde quedó mi pago") is True


def test_cross_set_catches_exact_and_near():
    """Train/test, message/gold and T-303 checks share one helper."""
    train = [("train-1", "quiero cancelar mi transferencia pendiente de ayer")]
    test_same = [("test-1", "quiero cancelar mi transferencia pendiente de ayer")]
    assert ms.check_cross_set(train, test_same, "train", "test")
    test_far = [("test-1", "buenos días, ¿cuál es el horario de la sucursal?")]
    assert ms.check_cross_set(train, test_far, "train", "test") == []


# Registry schemas.


def test_rewording_row_carries_parent_reference():
    """Rewordings are new seeds: fresh key, parent recorded, hash shared."""
    row = SeedRow.model_validate(
        {
            "seed_key": "v1-rewording1",
            "split": "test",
            "prompt_id": "test-v1",
            "kind": "rewording",
            "parent_seed_key": "v1-parentseed",
            "customer_hash": "0123456789abcdef",
            "country_variant": "CO",
            "record_facts": {"kind": "rewording", "status": "Pending"},
            "event_date": "2026-02-10",
            "policy_version": "v2",
        }
    )
    assert row.parent_seed_key == "v1-parentseed"


def test_hand_written_row_has_no_parent_or_record():
    """Hand-written rows are new seeds with nominal facts and no parent."""
    row = SeedRow.model_validate(
        {
            "seed_key": "v1-handmade01",
            "split": "test",
            "prompt_id": "hand-written",
            "kind": "hand_written",
            "customer_hash": "fedcba9876543210",
            "country_variant": "AR",
            "record_facts": {"kind": "hand_written", "status": "Declined"},
            "event_date": "2026-03-01",
            "policy_version": "v2",
        }
    )
    assert row.parent_seed_key is None


def test_portuguese_and_brl_rejected():
    """Portuguese variants and BRL never enter the set (T-203 owns them)."""
    with pytest.raises(ValidationError):
        make_message(language_variant="pt-BR")
    with pytest.raises(ValidationError):
        make_seed(record_facts={"kind": "problem_transaction", "currency": "BRL"})


def test_no_customer_record_fields_committed():
    """Raw id-shaped keys are not part of the committed schema."""
    with pytest.raises(ValidationError):
        SeedRow.model_validate(
            {
                "seed_key": "v1-abc",
                "split": "train",
                "prompt_id": "train-v1",
                "kind": "problem_transaction",
                "customer_id": "C-123",
                "customer_hash": "0123456789abcdef",
                "country_variant": "MX",
                "record_facts": {"kind": "problem_transaction"},
                "event_date": "2024-03-10",
                "policy_version": "v2",
            }
        )


# Full registry checks.


def green_inputs() -> dict:
    """One passing registry world: disjoint hashes, ordered dates, fresh keys."""
    seeds = {
        "train": [make_seed(seed_key="v1-t1", customer_hash="a" * 16)],
        "calibration": [
            make_seed(
                seed_key="v1-c1",
                split="calibration",
                prompt_id="train-v1",
                customer_hash="b" * 16,
                event_date="2025-08-10",
            )
        ],
        "test": [
            make_seed(
                seed_key="v1-e1",
                split="test",
                prompt_id="test-v1",
                customer_hash="c" * 16,
                event_date="2026-02-10",
            )
        ],
    }
    messages = {
        "train": [make_message()],
        "calibration": [
            make_message(
                msg_id="cal-0001",
                split="calibration",
                seed_key="v1-c1",
                message="Mi pago sigue pendiente desde ayer, ¿lo revisan?",
            )
        ],
        "test": [
            make_message(
                msg_id="test-0001",
                split="test",
                seed_key="v1-e1",
                message="Se cayó la aplicación a mitad del envío, ¿se hizo el cobro?",
            )
        ],
    }
    return {
        "seeds": seeds,
        "messages": messages,
        "record_ids": {"train": ["r-t1"], "calibration": ["r-c1"], "test": ["r-e1"]},
        "gold_hashes": {"d" * 16},
        "gold_keys": {"v1-gold1"},
        "gold_texts": ["un mensaje dorado completamente distinto sobre horarios"],
        "t303_texts": ["un caso t303 completamente distinto sobre comisiones"],
        "template_texts": {"plantilla de transcripción del conjunto de datos"},
    }


def test_registry_checks_green_on_clean_world():
    """A clean synthetic world passes every registry check."""
    report = ms.run_registry_checks(**green_inputs())
    assert report.passed, [v.detail for v in report.violations]


def test_l1_fires_across_splits_not_within_test():
    """A hash shared across splits fails L1; a parent/rewording pair inside
    test never does (L1 compares across splits only)."""
    inputs = green_inputs()
    inputs["seeds"]["test"].append(
        make_seed(
            seed_key="v1-e2",
            split="test",
            prompt_id="test-v1",
            kind="rewording",
            parent_seed_key="v1-e1",
            customer_hash="c" * 16,
            event_date="2026-02-11",
        )
    )
    inputs["record_ids"]["test"].append("r-e2")
    assert ms.run_registry_checks(**inputs).passed
    inputs["seeds"]["calibration"][0] = make_seed(
        seed_key="v1-c1",
        split="calibration",
        prompt_id="train-v1",
        customer_hash="c" * 16,
        event_date="2025-08-10",
    )
    report = ms.run_registry_checks(**inputs)
    assert any(v.rule_id == "L1" for v in report.violations)


def test_l2_fires_on_future_train_record():
    """A train record at or after the calibration start fails L2."""
    inputs = green_inputs()
    inputs["seeds"]["train"][0] = make_seed(event_date="2025-06-01")
    report = ms.run_registry_checks(**inputs)
    assert any(v.rule_id == "L2" for v in report.violations)


def test_l3_catches_inserted_template():
    """A message copying dataset text fails the no-duplication scan."""
    inputs = green_inputs()
    inputs["messages"]["train"][0] = make_message(
        message="plantilla de transcripción del conjunto de datos"
    )
    report = ms.run_registry_checks(**inputs)
    assert any(v.rule_id == "L3" for v in report.violations)


def test_l4_fires_on_shared_seed_key():
    """One seed key feeding two splits fails generation isolation."""
    inputs = green_inputs()
    inputs["seeds"]["test"][0] = make_seed(
        seed_key="v1-t1",
        split="test",
        prompt_id="test-v1",
        customer_hash="c" * 16,
        event_date="2026-02-10",
    )
    report = ms.run_registry_checks(**inputs)
    assert any(v.rule_id == "L4" for v in report.violations)


def test_l5_fires_on_gold_in_train():
    """A gold key reused in train fails the held-out check."""
    inputs = green_inputs()
    inputs["seeds"]["train"][0] = make_seed(seed_key="v1-gold1")
    report = ms.run_registry_checks(**inputs)
    assert any(v.rule_id == "L5" for v in report.violations)


def test_t303_quarantine_catches_case_text():
    """A set message matching a T-303 case text fails under its own name."""
    inputs = green_inputs()
    inputs["messages"]["test"][0] = make_message(
        msg_id="test-0001",
        split="test",
        seed_key="v1-e1",
        message="un caso t303 completamente distinto sobre comisiones",
    )
    report = ms.run_registry_checks(**inputs)
    assert any("T-303 quarantine" in v.detail for v in report.violations)


def test_stratum_audit_flags_small_cells_and_splits_review():
    """Cells under 30 are flagged, never failed, with reviewed counts apart."""
    message = make_message()
    audit = ms.stratum_audit([message])
    key = "train|es-MX|explain"
    assert audit[key]["n"] == 1
    assert audit[key]["under_30"] is True
    assert audit[key]["unreviewed"] == 1
    reviewed = make_message(
        provenance=MessageProvenance.model_validate(
            {
                "prompt_id": "train-v1",
                "prompt_version": "v1",
                "model_id": "Qwen/Qwen3.6-35B-A3B-FP8",
                "reviewer": "Kevin Vicent",
                "review_verdict": "pass",
            }
        )
    )
    audit = ms.stratum_audit([message, reviewed])
    assert audit[key]["reviewed"] == 1
    assert audit[key]["unreviewed"] == 1
