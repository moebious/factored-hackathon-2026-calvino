"""Tests for the fine-tuning export and its CLI (TSD-020, T-202).

Offline, on the synthetic fixtures in ``tests/fixtures/message-set/v1``. Each leakage rule fails
once on a copy of the fixture with one deliberate violation, and in every failure nothing may be
written.
"""

import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

from calvino.classifiers.finetune_record import DataManifest
from calvino.classifiers.laya import needs_human_question, workflow_area_question
from calvino.data.finetune_export import (
    HOLDOUT_MAX_ITEMS,
    ROLE_HOLDOUT,
    ROLE_TRAIN,
    LeakageError,
    _holdout_message_ids,
    build_items,
    export_train_split,
    load_guard_inputs,
    question_schema_sha256,
)

REPO = Path(__file__).resolve().parents[3]
FIXTURE = REPO / "tests" / "fixtures" / "message-set" / "v1"

# Pinned on purpose. A change to either question builder (wording, criteria or option order)
# changes this hash and fails the test below until the export is regenerated and the pin is
# updated deliberately: a checkpoint trained on different wording is a different experiment.
PINNED_SCHEMA_SHA256 = "abd8431deb8702f6dfb3d2c473e32689570c99cd34782858312fc01521cf60e4"

SCRIPT = REPO / "scripts" / "export_finetune_dataset.py"
_spec = importlib.util.spec_from_file_location("export_finetune_dataset", SCRIPT)
assert _spec is not None and _spec.loader is not None
cli = importlib.util.module_from_spec(_spec)
sys.modules["export_finetune_dataset"] = cli
_spec.loader.exec_module(cli)


def copy_fixture(tmp_path: Path) -> Path:
    target = tmp_path / "v1"
    shutil.copytree(FIXTURE, target)
    return target


def reaccept(set_dir: Path) -> None:
    """Re-sign the acceptance after a deliberate edit, so only the planted violation can fail."""
    acceptance = json.loads((set_dir / "acceptance.json").read_text())
    digest = hashlib.sha256((set_dir / "train.jsonl").read_bytes()).hexdigest()
    acceptance["splits"]["train"]["messages_sha256"] = digest
    (set_dir / "acceptance.json").write_text(json.dumps(acceptance))


def edit_train(set_dir: Path, change) -> None:
    rows = [json.loads(line) for line in (set_dir / "train.jsonl").read_text().splitlines()]
    change(rows)
    (set_dir / "train.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"
    )
    reaccept(set_dir)


def inputs_for(set_dir: Path, eval_messages=()):
    return load_guard_inputs(
        set_dir=set_dir, gold_path=set_dir / "gold.jsonl", eval_messages=list(eval_messages)
    )


def failed_checks(error: LeakageError) -> set[str]:
    return {check.check for check in error.result.checks if not check.passed}


def assert_refused(set_dir: Path, tmp_path: Path, expected: str, eval_messages=()) -> LeakageError:
    out = tmp_path / "out"
    with pytest.raises(LeakageError) as raised:
        export_train_split(inputs_for(set_dir, eval_messages), out, "test-sha")
    assert expected in failed_checks(raised.value)
    assert not out.exists(), "a refused export must write nothing"
    return raised.value


# --- the happy path -----------------------------------------------------------------------


def test_the_fixture_exports_the_expected_items(tmp_path: Path):
    manifest = export_train_split(inputs_for(FIXTURE), tmp_path / "out", "test-sha")
    items = [json.loads(x) for x in (tmp_path / "out" / "items.jsonl").read_text().splitlines()]

    assert len(items) == 11  # 6 kept messages: 6 needs_human items + 5 area items (t-006 has none)
    by_id = {item["item_id"]: item for item in items}
    assert by_id["t-004:needs_human"]["target_option"] == "human needed"
    assert by_id["t-001:needs_human"]["target_option"] == "can handle automatically"
    assert by_id["t-004:workflow_area"]["target_option"] == "dispute or unrecognised charge"
    assert "t-006:workflow_area" not in by_id and "t-006:needs_human" in by_id
    assert "t-007:needs_human" not in by_id  # review verdict fail: removed from the split
    first = by_id["t-001:needs_human"]
    assert first["state"] == "¿Dónde está mi transferencia de 4,500 MXN?"
    assert first["question"] == needs_human_question()
    assert by_id["t-001:workflow_area"]["question"] == workflow_area_question()
    assert manifest["counts"]["needs_human"] == {"human needed": 1, "can handle automatically": 5}
    assert manifest["counts"]["workflow_area"]["stuck payment"] == 3
    assert manifest["counts"]["workflow_area"]["fraud or stolen access"] == 0
    assert manifest["reviewed"] == 2 and manifest["unreviewed"] == 4
    assert manifest["excluded"] == {
        "review verdict fail (removed from the split)": 1,
        "workflow area unset (no area item)": 1,
    }
    assert all(check["passed"] for check in manifest["leakage_guard"])


def test_option_order_survives_the_file_because_it_is_positional_in_laya(tmp_path: Path):
    export_train_split(inputs_for(FIXTURE), tmp_path / "out", "test-sha")
    lines = (tmp_path / "out" / "items.jsonl").read_text(encoding="utf-8").splitlines()
    expected = {
        "needs_human": list(needs_human_question()["criteria"]),
        "workflow_area": list(workflow_area_question()["criteria"]),
    }
    for line in lines:
        item = json.loads(line)
        assert list(item["question"]["criteria"]) == expected[item["question_id"]]
    # dict equality ignores order, so check the question text in the file itself
    assert expected["needs_human"] == ["human needed", "can handle automatically"]
    assert '"human needed": ' in lines[0] and lines[0].index("human needed") < lines[0].index(
        "can handle automatically"
    )


def test_the_export_is_byte_identical_on_a_second_run(tmp_path: Path):
    for name in ("one", "two"):
        export_train_split(inputs_for(FIXTURE), tmp_path / name, "test-sha")
    for name in ("items.jsonl", "manifest.json"):
        assert (tmp_path / "one" / name).read_bytes() == (tmp_path / "two" / name).read_bytes()


def test_the_manifest_hashes_describe_the_files(tmp_path: Path):
    manifest = export_train_split(inputs_for(FIXTURE), tmp_path / "out", "test-sha")
    assert (
        manifest["items_sha256"]
        == hashlib.sha256((tmp_path / "out" / "items.jsonl").read_bytes()).hexdigest()
    )
    assert (
        manifest["input_sha256"]
        == hashlib.sha256((FIXTURE / "train.jsonl").read_bytes()).hexdigest()
    )
    assert json.loads((tmp_path / "out" / "manifest.json").read_text()) == manifest


def test_the_manifest_fits_the_run_record(tmp_path: Path):
    manifest = export_train_split(inputs_for(FIXTURE), tmp_path / "out", "test-sha")
    fields = {name: manifest[name] for name in DataManifest.model_fields}
    assert DataManifest.model_validate(fields).exporter_git_sha == "test-sha"


def test_an_export_is_never_overwritten(tmp_path: Path):
    export_train_split(inputs_for(FIXTURE), tmp_path / "out", "test-sha")
    with pytest.raises(FileExistsError, match="never overwritten"):
        export_train_split(inputs_for(FIXTURE), tmp_path / "out", "test-sha")


def test_the_question_schema_hash_is_pinned():
    assert question_schema_sha256() == PINNED_SCHEMA_SHA256, (
        "a question builder changed: regenerate the export and update the pin on purpose"
    )


# --- the temperature hold-out -------------------------------------------------------------


def test_the_holdout_is_by_message_and_follows_the_notebooks_size_rule():
    rows = inputs_for(FIXTURE).train
    items, _ = build_items([r for r in rows if r.provenance.review_verdict != "fail"])
    roles_by_message: dict[str, set[str]] = {}
    for item in items:
        roles_by_message.setdefault(item["msg_id"], set()).add(item["role"])
    assert all(len(roles) == 1 for roles in roles_by_message.values())  # a message never splits
    held = [i for i in items if i["role"] == ROLE_HOLDOUT]
    assert len(held) >= len(items) // 10 and {i["role"] for i in items} == {
        ROLE_TRAIN,
        ROLE_HOLDOUT,
    }


def test_the_holdout_is_capped_at_the_notebooks_400_items_and_is_deterministic():
    counts = {f"m-{n:05d}": 2 for n in range(5000)}
    chosen = _holdout_message_ids(counts)
    assert sum(counts[m] for m in chosen) == HOLDOUT_MAX_ITEMS
    assert chosen == _holdout_message_ids(counts)


def test_a_tiny_split_holds_out_nothing():
    assert _holdout_message_ids({"a": 2, "b": 2, "c": 1}) == set()  # 5 items // 10 == 0


# --- one failing fixture per leakage rule -------------------------------------------------


def test_a_missing_acceptance_record_blocks_the_export(tmp_path: Path):
    set_dir = copy_fixture(tmp_path)
    (set_dir / "acceptance.json").unlink()
    error = assert_refused(set_dir, tmp_path, "wrong-split")
    assert "acceptance record missing" in error.result.summary()


def test_editing_the_messages_after_acceptance_blocks_the_export(tmp_path: Path):
    set_dir = copy_fixture(tmp_path)
    rows = (set_dir / "train.jsonl").read_text().replace("sigue pendiente", "sigue retenido")
    (set_dir / "train.jsonl").write_text(rows)  # not re-signed on purpose
    error = assert_refused(set_dir, tmp_path, "wrong-split")
    assert "changed after acceptance" in error.result.summary()


def test_a_calibration_row_in_train_blocks_the_export(tmp_path: Path):
    set_dir = copy_fixture(tmp_path)

    def plant(rows):
        rows[0]["message"] = "Mi pago sigue pendiente desde el lunes"  # c-001's text

    edit_train(set_dir, plant)
    assert_refused(set_dir, tmp_path, "text-overlap")


def test_a_gold_overlap_blocks_the_export(tmp_path: Path):
    set_dir = copy_fixture(tmp_path)
    edit_train(set_dir, lambda rows: rows[0].update(message="Por favor revisen mi reclamo abierto"))
    assert_refused(set_dir, tmp_path, "text-overlap")


def test_an_evaluation_case_overlap_blocks_the_export(tmp_path: Path):
    set_dir = copy_fixture(tmp_path)
    edit_train(set_dir, lambda rows: rows[0].update(message="Reintentar transferencia E-US-001"))
    assert_refused(
        set_dir, tmp_path, "text-overlap", [("ORC-001", "reintentar transferencia e-us-001")]
    )


def test_a_shared_seed_key_blocks_the_export(tmp_path: Path):
    set_dir = copy_fixture(tmp_path)
    seeds = [json.loads(x) for x in (set_dir / "seeds.calibration.jsonl").read_text().splitlines()]
    seeds[0]["seed_key"] = "k-train-1"
    (set_dir / "seeds.calibration.jsonl").write_text("\n".join(json.dumps(s) for s in seeds) + "\n")
    assert_refused(set_dir, tmp_path, "shared-keys")


def test_a_shared_customer_hash_blocks_the_export(tmp_path: Path):
    set_dir = copy_fixture(tmp_path)
    seeds = [json.loads(x) for x in (set_dir / "seeds.test.jsonl").read_text().splitlines()]
    seeds[0]["customer_hash"] = "ct1"
    (set_dir / "seeds.test.jsonl").write_text("\n".join(json.dumps(s) for s in seeds) + "\n")
    assert_refused(set_dir, tmp_path, "shared-keys")


def test_a_portuguese_row_blocks_the_export(tmp_path: Path):
    set_dir = copy_fixture(tmp_path)

    def plant(rows):
        rows[1]["language_variant"] = "pt-BR"

    edit_train(set_dir, plant)
    assert_refused(set_dir, tmp_path, "portuguese-row")


def test_an_unknown_label_blocks_the_export(tmp_path: Path):
    set_dir = copy_fixture(tmp_path)
    edit_train(set_dir, lambda rows: rows[0]["labels"].update(workflow_area="banking"))
    assert_refused(set_dir, tmp_path, "unknown-label")


def test_a_missing_comparison_set_fails_closed(tmp_path: Path):
    set_dir = copy_fixture(tmp_path)
    (set_dir / "test.jsonl").unlink()
    error = assert_refused(set_dir, tmp_path, "text-overlap")
    assert "test messages unavailable" in error.result.summary()


# --- the CLI ------------------------------------------------------------------------------


def run_cli(*argv: str) -> int:
    return cli.main([*argv])


def test_the_cli_exports_the_fixture(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    code = run_cli(
        "--out",
        str(tmp_path / "out"),
        "--set-dir",
        str(FIXTURE),
        "--gold",
        str(FIXTURE / "gold.jsonl"),
    )
    assert code == 0 and (tmp_path / "out" / "manifest.json").is_file()
    assert "exported 11 items" in capsys.readouterr().out


def test_the_cli_exits_1_and_names_the_offender_when_the_guard_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    set_dir = copy_fixture(tmp_path)
    (set_dir / "acceptance.json").unlink()
    code = run_cli(
        "--out",
        str(tmp_path / "out"),
        "--set-dir",
        str(set_dir),
        "--gold",
        str(set_dir / "gold.jsonl"),
    )
    assert code == 1 and "wrong-split" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_the_cli_exits_2_when_the_split_file_is_missing(tmp_path: Path):
    assert run_cli("--out", str(tmp_path / "out"), "--set-dir", str(tmp_path / "nowhere")) == 2
