"""Tests for the fine-tuning run record and its writers (TSD-020, T-202).

Offline: the fixture is a synthetic record (no run happened), and every test builds
variations of it. The record must refuse what a valid run could not have produced, and
the Markdown must claim no accuracy.
"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from calvino.classifiers.finetune_record import (
    REQUIRED_LEAKAGE_CHECKS,
    TRAIN_FIT_LABEL,
    FineTuneRunRecord,
    load_run_record,
    record_json,
    render_markdown,
    write_run_record,
)

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "finetune" / "synthetic_run_record.json"
)


def fixture_data() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def make(**changes) -> FineTuneRunRecord:
    data = fixture_data()
    for dotted, value in changes.items():
        *path, leaf = dotted.split("__")
        node = data
        for key in path:
            node = node[key]
        node[leaf] = value
    return FineTuneRunRecord.model_validate(data)


def test_the_fixture_record_validates():
    record = load_run_record(FIXTURE)
    assert record.stem == "T-202-2026-10-20-333333333333"
    assert record.base.revision != record.output.revision


def test_output_must_differ_from_the_base():
    with pytest.raises(ValidationError, match="must differ from the base"):
        make(output__sha256=fixture_data()["base"]["sha256"])
    with pytest.raises(ValidationError, match="must differ from the base"):
        make(output__revision=fixture_data()["base"]["revision"])


def test_tag_must_match_the_run_number():
    with pytest.raises(ValidationError, match="t202-run1"):
        make(output__tag="t202-run2")


@pytest.mark.parametrize("field", ["revision", "sha256"])
def test_pins_must_be_full_lowercase_hex(field):
    with pytest.raises(ValidationError):
        make(**{f"output__{field}": "ABC"})


def test_effective_batch_must_match_the_settings():
    with pytest.raises(ValidationError, match="effective_batch 32"):
        make(configuration__effective_batch=32)


def test_one_loss_value_per_epoch():
    with pytest.raises(ValidationError, match="one value per epoch"):
        make(training__loss_per_epoch=[0.9, 0.6])


def test_train_fit_is_a_fraction_and_not_empty():
    with pytest.raises(ValidationError, match="within"):
        make(training__train_fit={"needs_human": 97.0})
    with pytest.raises(ValidationError, match="at least one question"):
        make(training__train_fit={})


def test_a_failed_leakage_check_blocks_the_record():
    checks = fixture_data()["leakage_guard"]
    checks[1] = {"check": "text-overlap", "passed": False}
    with pytest.raises(ValidationError, match="leakage guard failed.*text-overlap"):
        make(leakage_guard=checks)


def test_every_required_leakage_check_must_be_reported():
    checks = [c for c in fixture_data()["leakage_guard"] if c["check"] != "shared-keys"]
    with pytest.raises(ValidationError, match="did not report: shared-keys"):
        make(leakage_guard=checks)
    assert set(REQUIRED_LEAKAGE_CHECKS) == {c["check"] for c in fixture_data()["leakage_guard"]}


def test_unknown_fields_and_bad_dates_are_refused():
    with pytest.raises(ValidationError):
        make(accuracy=0.99)
    with pytest.raises(ValidationError):
        make(run_date="last tuesday")


def test_markdown_labels_every_training_metric_and_names_both_checkpoints():
    record = load_run_record(FIXTURE)
    markdown = render_markdown(record)
    metric_rows = [
        line for line in markdown.splitlines() if line.startswith(("| Loss,", "| Train fit,"))
    ]
    assert len(metric_rows) == 4 + 2
    assert all(TRAIN_FIT_LABEL in row for row in metric_rows)
    for pin in (
        record.base.revision,
        record.base.sha256,
        record.output.revision,
        record.output.sha256,
    ):
        assert pin in markdown
    assert (
        "convaiinnovations/laya/multilingual" in markdown and "kevago/calvino-laya-ft" in markdown
    )


def test_markdown_claims_no_accuracy_and_points_to_t201():
    markdown = render_markdown(load_run_record(FIXTURE))
    assert "no Laya accuracy" in markdown and "T-201" in markdown
    # A fit appears only inside the labelled training table.
    assert "accuracy:" not in markdown.lower()


def test_markdown_lists_deviations_with_their_reason():
    data = fixture_data()
    data["configuration"]["deviations"] = [{"setting": "epochs", "reason": "memory limit"}]
    markdown = render_markdown(FineTuneRunRecord.model_validate(data))
    assert "- **epochs**: memory limit" in markdown
    assert "No deviation from TSD-020." in render_markdown(load_run_record(FIXTURE))


def test_json_is_stable_and_round_trips():
    record = load_run_record(FIXTURE)
    assert record_json(record) == record_json(record)
    assert FineTuneRunRecord.model_validate_json(record_json(record)) == record


def test_write_creates_both_files_and_never_overwrites(tmp_path: Path):
    record = load_run_record(FIXTURE)
    md_path, json_path = write_run_record(record, tmp_path)
    assert md_path.name == "T-202-2026-10-20-333333333333.md"
    assert json_path.name == "T-202-2026-10-20-333333333333.json"
    assert load_run_record(json_path) == record
    with pytest.raises(FileExistsError, match="never overwritten"):
        write_run_record(record, tmp_path)


def test_the_loop_settings_are_required_and_validated():
    data = fixture_data()
    del data["configuration"]["loop"]
    with pytest.raises(ValidationError, match="loop"):
        FineTuneRunRecord.model_validate(data)
    with pytest.raises(ValidationError):
        make(configuration__loop__loss="something else")
    with pytest.raises(ValidationError):
        make(configuration__loop__sigma_start=0)


def test_markdown_records_the_loop_settings_the_notebook_fixes_in_code():
    markdown = render_markdown(load_run_record(FIXTURE))
    assert "| Loss | policy gradient + soft cross-entropy (cross-entropy weight 1) |" in markdown
    assert "| Exploration noise | 0.4 to 0.1 |" in markdown
    assert "| Reward weights (spherical / RPS) | 0.75 / 1 |" in markdown
    assert "| Sequence lengths (item / head) | 1024 / 256 |" in markdown
    assert "| Temperature hold-out | min(400, 10% of items), chosen by message |" in markdown


def test_markdown_says_laya_temperatures_are_not_calvinos_calibration():
    markdown = render_markdown(load_run_record(FIXTURE))
    assert "choice 1.180" in markdown and "not Calvino's calibration" in markdown
    data = fixture_data()
    data["training"]["laya_temperatures"] = {}
    assert "laya's own temperatures" not in render_markdown(FineTuneRunRecord.model_validate(data))
