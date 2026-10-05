"""Tests for the acceptance record and the fine-tuning leakage guard (TSD-020, T-202).

Synthetic rows only: no network, GPU, keys, dataset or salt. Every check has one passing
baseline and one failing case per way it can fail, and the guard must fail closed when a
comparison set is missing.
"""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

from calvino.data.finetune_guard import (
    CHECK_NAMES,
    MAX_ACCEPTED_DEFECTS,
    AcceptanceRecord,
    GuardInputs,
    SplitAcceptance,
    load_acceptance,
    load_message_rows,
    needs_human_option,
    run_leakage_guard,
)
from calvino.data.labels import GoldRecord
from calvino.data.message_set import MessageRow, SeedRow

DIGEST = "a" * 64
GATE_HASH = "b" * 16


def seed(key: str, split: str, customer: str, prompt: str = "train-v1") -> SeedRow:
    return SeedRow.model_validate(
        {
            "seed_key": key,
            "split": split,
            "prompt_id": prompt,
            "kind": "problem_transaction",
            "customer_hash": customer,
            "country_variant": "MX",
            "record_facts": {
                "kind": "problem_transaction",
                "status": "Pending",
                "amount_band": "under_gate",
                "currency": "MXN",
            },
            "event_date": "2024-03-10",
            "policy_version": "v2",
            "gate_table_hash": GATE_HASH,
        }
    )


def message(
    msg_id: str, text: str, split: str, key: str, intent: str = "explain", **labels
) -> MessageRow:
    return MessageRow.model_validate(
        {
            "msg_id": msg_id,
            "split": split,
            "language_variant": "es-MX",
            "message": text,
            "seed_key": key,
            "labels": {
                "workflow_area": "stuck payment",
                "stuck_intent": "status",
                "clear_enough": True,
                "needs_person": False,
                "injection": False,
                **labels,
            },
            "oracle_facts": {
                "intent": intent,
                "ambiguous": False,
                "status": "Pending",
                "owner": True,
                "amount_band": "under_gate",
                "fraud_flag": False,
                "in_scope": True,
            },
            "provenance": {
                "prompt_id": f"{split}-v1",
                "prompt_version": "v1",
                "model_id": "Qwen/Qwen3.6-35B-A3B-FP8",
                "review_verdict": "unreviewed",
            },
        }
    )


def gold(gold_id: str, text: str, seed_ref: str = "hand-written") -> GoldRecord:
    return GoldRecord(
        gold_id=gold_id,
        rubric_version="v1",
        message=text,
        language_variant="es-MX",
        seed_ref=seed_ref,
    )


def accepted(defects: int = 0, sha: str = DIGEST, version: str = "v1") -> AcceptanceRecord:
    return AcceptanceRecord(
        set_version=version,
        splits={
            "train": SplitAcceptance(
                accepted=True,
                defects=defects,
                reviewed_sample=30,
                prompt_version="train-v1",
                messages_sha256=sha,
                accepted_on="2026-10-20",
            )
        },
    )


def clean_inputs() -> GuardInputs:
    """A train split that passes every check against disjoint other sets."""
    return GuardInputs(
        train=[
            message("train-1", "¿Dónde está mi transferencia de 4,500 MXN?", "train", "k-train-1"),
            message("train-2", "Quiero cancelar el giro que mandé ayer", "train", "k-train-2"),
        ],
        train_seeds=[seed("k-train-1", "train", "c1"), seed("k-train-2", "train", "c2")],
        set_version="v1",
        messages_sha256=DIGEST,
        acceptance=accepted(),
        calibration=[
            message("cal-1", "Mi pago sigue pendiente desde el lunes", "calibration", "k-cal-1")
        ],
        test=[message("test-1", "Necesito saber el estado de mi retiro", "test", "k-test-1")],
        calibration_seeds=[seed("k-cal-1", "calibration", "c3", "cal-v1")],
        test_seeds=[seed("k-test-1", "test", "c4", "test-v1")],
        gold=[gold("G-1", "Por favor revisen mi reclamo abierto")],
        eval_messages=[("ORC-001", "Reintentar transferencia E-US-001")],
    )


def result(inputs: GuardInputs):
    return {check.check: check for check in run_leakage_guard(inputs).checks}


def test_a_clean_split_passes_all_five_checks_in_order():
    outcome = run_leakage_guard(clean_inputs())
    assert outcome.passed and outcome.summary() == ""
    assert tuple(check.check for check in outcome.checks) == CHECK_NAMES


# --- wrong-split and the acceptance record ------------------------------------------------


def test_a_row_that_is_not_train_fails_wrong_split():
    inputs = clean_inputs()
    inputs = replace(
        inputs,
        train=[message("c-9", "Mi pago no llegó", "calibration", "k-train-1"), *inputs.train],
    )
    check = result(inputs)["wrong-split"]
    assert not check.passed and "c-9: split is calibration" in check.offenders[0]


def test_missing_acceptance_fails_closed():
    check = result(replace(clean_inputs(), acceptance=None))["wrong-split"]
    assert not check.passed and "acceptance record missing" in check.offenders


def test_acceptance_without_a_train_entry_fails():
    empty = AcceptanceRecord(set_version="v1", splits={})
    assert not result(replace(clean_inputs(), acceptance=empty))["wrong-split"].passed


@pytest.mark.parametrize(
    ("record", "reason"),
    [
        (accepted(defects=MAX_ACCEPTED_DEFECTS + 1), "exceed the limit"),
        (accepted(sha="c" * 64), "changed after acceptance"),
        (accepted(version="v2"), "not v1"),
    ],
)
def test_a_bad_acceptance_fails_wrong_split(record: AcceptanceRecord, reason: str):
    check = result(replace(clean_inputs(), acceptance=record))["wrong-split"]
    assert not check.passed and any(reason in offender for offender in check.offenders)


def test_one_defect_is_still_accepted():
    assert result(replace(clean_inputs(), acceptance=accepted(defects=1)))["wrong-split"].passed


def test_an_unaccepted_split_fails():
    record = accepted()
    unaccepted = record.model_copy(
        update={"splits": {"train": record.splits["train"].model_copy(update={"accepted": False})}}
    )
    check = result(replace(clean_inputs(), acceptance=unaccepted))["wrong-split"]
    assert "train split is not accepted" in check.offenders


# --- text-overlap -------------------------------------------------------------------------


def with_train_text(text: str) -> GuardInputs:
    inputs = clean_inputs()
    return replace(inputs, train=[message("train-9", text, "train", "k-train-1"), *inputs.train])


@pytest.mark.parametrize(
    ("text", "other"),
    [
        ("Mi pago sigue pendiente desde el lunes", "calibration cal-1"),
        ("¡Necesito saber el estado de mi retiro!", "test test-1"),  # punctuation only
        ("Por favor revisen mi reclamo abierto", "gold G-1"),
        ("reintentar transferencia e-us-001", "evaluation-cases ORC-001"),  # case only
    ],
)
def test_text_overlap_catches_exact_and_normalised_copies(text: str, other: str):
    check = result(with_train_text(text))["text-overlap"]
    assert not check.passed and f"train-9 overlaps {other}" in check.offenders


def test_text_overlap_catches_a_portuguese_set_copy():
    inputs = replace(
        with_train_text("Meu pagamento ainda está pendente"),
        portuguese_messages=[("PT-1", "Meu pagamento ainda está pendente")],
    )
    assert "train-9 overlaps portuguese PT-1" in result(inputs)["text-overlap"].offenders


def test_missing_comparison_messages_fail_closed():
    for name in ("calibration", "test"):
        check = result(replace(clean_inputs(), **{name: None}))["text-overlap"]
        assert not check.passed and f"{name} messages unavailable" in check.offenders[0]


# --- shared-keys --------------------------------------------------------------------------


def test_a_shared_customer_hash_fails():
    inputs = replace(clean_inputs(), test_seeds=[seed("k-test-1", "test", "c1", "test-v1")])
    assert any(o.startswith("L1") for o in result(inputs)["shared-keys"].offenders)


def test_a_shared_seed_key_fails():
    inputs = replace(
        clean_inputs(), calibration_seeds=[seed("k-train-1", "calibration", "c3", "cal-v1")]
    )
    assert any(o.startswith("L4") for o in result(inputs)["shared-keys"].offenders)


def test_a_gold_seed_in_train_fails():
    inputs = replace(clean_inputs(), gold=[gold("G-2", "otro texto", seed_ref="k-train-2")])
    assert any(o.startswith("L5") for o in result(inputs)["shared-keys"].offenders)


def test_a_train_message_whose_seed_is_unknown_fails():
    inputs = replace(
        clean_inputs(), train=[message("train-8", "texto nuevo", "train", "k-unknown")]
    )
    offenders = result(inputs)["shared-keys"].offenders
    assert "train-8: seed k-unknown is not in the train registry" in offenders


def test_missing_seed_registries_fail_closed():
    for name in ("calibration_seeds", "test_seeds"):
        check = result(replace(clean_inputs(), **{name: None}))["shared-keys"]
        assert not check.passed and "unavailable" in check.offenders[-1]


# --- portuguese-row and unknown-label -----------------------------------------------------


def test_a_non_spanish_train_row_fails():
    check = result(replace(clean_inputs(), non_spanish_train_ids=["train-77"]))["portuguese-row"]
    assert not check.passed and check.offenders == ("train-77: non-Spanish variant",)


def test_an_unknown_workflow_area_fails_but_an_unset_one_does_not():
    bad = replace(
        clean_inputs(),
        train=[message("train-6", "texto", "train", "k-train-1", workflow_area="banking")],
    )
    assert not result(bad)["unknown-label"].passed
    unset = replace(
        clean_inputs(),
        train=[
            message(
                "train-5",
                "asdf qwerty",
                "train",
                "k-train-1",
                intent="none",
                workflow_area=None,
                stuck_intent=None,
                clear_enough=False,
            )
        ],
    )
    assert result(unset)["unknown-label"].passed


def test_offenders_are_ids_and_reasons_never_message_text():
    inputs = with_train_text("Mi pago sigue pendiente desde el lunes")
    summary = run_leakage_guard(inputs).summary()
    assert "train-9" in summary and "pendiente" not in summary


def test_needs_person_maps_to_the_question_options():
    assert needs_human_option(True) == "human needed"
    assert needs_human_option(False) == "can handle automatically"


# --- loaders ------------------------------------------------------------------------------


def row_json(row: MessageRow, **overrides) -> str:
    return json.dumps({**row.model_dump(mode="json"), **overrides}, ensure_ascii=False)


def test_the_loader_sets_aside_non_spanish_rows_by_id(tmp_path: Path):
    good = message("train-1", "Hola, mi giro no llegó", "train", "k-train-1")
    path = tmp_path / "train.jsonl"
    path.write_text(
        row_json(good) + "\n" + row_json(good, msg_id="train-pt", language_variant="pt-BR") + "\n"
    )
    rows, non_spanish = load_message_rows(path)
    assert [row.msg_id for row in rows] == ["train-1"] and non_spanish == ["train-pt"]


def test_the_loader_reports_a_malformed_row_with_its_line(tmp_path: Path):
    path = tmp_path / "train.jsonl"
    path.write_text('{"msg_id": "x", "language_variant": "es-MX"}\n')
    with pytest.raises(SystemExit, match="train.jsonl:1: invalid message row"):
        load_message_rows(path)


def test_acceptance_loads_and_an_absent_file_means_nothing_is_accepted(tmp_path: Path):
    assert load_acceptance(tmp_path / "acceptance.json") is None
    path = tmp_path / "acceptance.json"
    path.write_text(accepted().model_dump_json())
    assert load_acceptance(path) == accepted()


@pytest.mark.parametrize("bad", [{"messages_sha256": "ABC"}, {"accepted_on": "last week"}])
def test_acceptance_entries_are_validated(bad: dict):
    fields = accepted().splits["train"].model_dump() | bad
    with pytest.raises(ValidationError):
        SplitAcceptance.model_validate(fields)
