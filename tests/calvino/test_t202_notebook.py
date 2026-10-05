"""Lint and contract tests for the T-202 Kaggle notebook (TSD-020).

Offline: nothing here runs the notebook, needs a GPU, laya or a token. The notebook is a JSON
file, so these tests read it as data, and execute only the small pure cells that the notebook marks
(`# CELL: ...`) against the synthetic fixtures, so the notebook cannot drift from the exporter's
output or from the run record's schema without a test failing.
"""

import ast
import json
import re
from pathlib import Path

import pytest

from calvino.classifiers.checkpoints import load_registry
from calvino.classifiers.finetune_record import FineTuneRunRecord
from calvino.data.finetune_export import export_train_split, load_guard_inputs

REPO = Path(__file__).resolve().parents[2]
NOTEBOOK = REPO / "notebooks" / "t202_laya_finetune_kaggle.ipynb"
FIXTURE = REPO / "tests" / "fixtures" / "message-set" / "v1"


def cells() -> list[dict]:
    return json.loads(NOTEBOOK.read_text(encoding="utf-8"))["cells"]


def source(cell: dict) -> str:
    return "".join(cell["source"])


def code_sources() -> list[str]:
    return [source(c) for c in cells() if c["cell_type"] == "code"]


def marked(marker: str) -> str:
    matches = [s for s in code_sources() if s.startswith(f"# CELL: {marker}")]
    assert len(matches) == 1, f"expected one cell marked {marker!r}"
    return matches[0]


def writefile_body(path_suffix: str) -> str:
    for text in code_sources():
        first, _, body = text.partition("\n")
        if first.startswith("%%writefile") and first.endswith(path_suffix):
            return body
    raise AssertionError(f"no %%writefile cell for {path_suffix}")


def python_part(text: str) -> str:
    """The Python of a cell: drop the `%%writefile` header and `!` shell lines."""
    lines = text.splitlines()
    if lines and lines[0].startswith("%%writefile"):
        lines = lines[1:]
    return "\n".join("" if line.lstrip().startswith("!") else line for line in lines)


# --- lint ---------------------------------------------------------------------------------


def test_the_notebook_is_committed_clean():
    document = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    assert document["nbformat"] == 4
    for cell in document["cells"]:
        if cell["cell_type"] == "code":
            assert cell["outputs"] == [] and cell["execution_count"] is None


def test_every_python_cell_parses():
    for text in code_sources():
        ast.parse(python_part(text))


def test_it_pins_laya_0_3_24_and_asserts_it():
    install = next(s for s in code_sources() if "pip install" in s)
    assert '"laya==0.3.24"' in install and 'assert laya.__version__ == "0.3.24"' in install
    assert "laya>=" not in "\n".join(code_sources())


def test_no_token_shaped_string_appears_anywhere():
    text = NOTEBOOK.read_text(encoding="utf-8")
    for pattern in (
        r"hf_[A-Za-z0-9]{16,}",
        r"ghp_[A-Za-z0-9]{16,}",
        r"sk-[A-Za-z0-9]{16,}",
        r"Bearer ",
    ):
        assert not re.search(pattern, text), pattern


def test_the_hub_token_is_read_only_from_kaggle_secrets():
    code = "\n".join(code_sources())
    assert 'UserSecretsClient().get_secret("HF_TOKEN")' in code
    for occurrence in re.finditer(r"HF_TOKEN", code):
        assert code[max(0, occurrence.start() - 12) : occurrence.start()].endswith('get_secret("')
    assert "login(" not in code and 'environ["HF_TOKEN"]' not in code
    assert 'environ.get("HF_TOKEN"' not in code


def test_no_vendor_benchmark_or_comparison_cell_survives():
    code = "\n".join(code_sources()).lower()
    for forbidden in ("load_dataset", "localllama", "typesafe", "benchmark", "jev"):
        assert forbidden not in code, forbidden


def test_the_header_credits_the_vendor_and_lists_the_changes():
    header = source(cells()[0])
    for expected in ("NandhaKishorM/laya", "Apache License 2.0", "6ea584941d", "TSD-020"):
        assert expected in header
    assert "train fit, not evaluation" in header
    assert len(re.findall(r"^\d+\. ", header, flags=re.M)) == 10


def test_the_published_run_is_a_new_tagged_commit_that_is_never_overwritten():
    push = marked("push")
    assert "list_repo_refs" in push and "already exists" in push
    assert "create_tag" in push and 'f"t202-run{RUN_NUMBER}"' in push
    assert "lfs.sha256 == OUTPUT_SHA256" in push


def test_the_training_script_seeds_torch_and_keeps_training_overrides_out_of_the_published_config():
    script = writefile_body("train_ddp.py")
    assert "torch.manual_seed(" in script and "torch.cuda.manual_seed_all(" in script
    assert "saved_config" in script and "published = dict(saved_config)" in script
    assert (
        "gradient_checkpointing"
        not in script.split("published = dict(saved_config)")[1].split("handle")[0]
    )


def test_dropped_items_stop_the_run():
    items = marked("items")
    assert "assert not dropped" in items


# --- the notebook agrees with the repository -----------------------------------------------


def test_the_pinned_base_equals_classifiers_yaml():
    namespace: dict = {}
    exec(marked("constants"), namespace)
    base = load_registry().get("base")
    assert namespace["BASE_REPO"] == base.repo
    assert namespace["BASE_SUBFOLDER"] == base.subfolder
    assert namespace["BASE_REVISION"] == base.revision
    assert namespace["BASE_SHA256"] == base.sha256


def test_the_published_run_is_the_calvino_model_repo():
    namespace: dict = {}
    exec(marked("constants"), namespace)
    assert namespace["OUTPUT_REPO"] == "kevago/calvino-laya-ft"
    assert namespace["NOTEBOOK_PATH"] == "notebooks/t202_laya_finetune_kaggle.ipynb"
    assert namespace["RULE_R_MIN_FIT"] == 0.90  # decision 42


# --- the pure cells, run against the fixtures ---------------------------------------------


@pytest.fixture
def fixture_export(tmp_path: Path) -> Path:
    inputs = load_guard_inputs(set_dir=FIXTURE, gold_path=FIXTURE / "gold.jsonl", eval_messages=[])
    export_train_split(inputs, tmp_path / "export", "test-sha")
    return tmp_path / "export"


def verify_namespace() -> dict:
    namespace = {"__name__": "test"}
    exec(marked("verify-export"), namespace)
    return namespace


def test_verify_export_accepts_the_exporters_output(fixture_export: Path):
    rows, manifest = verify_namespace()["verify_export"](str(fixture_export))
    assert (
        len(rows) == 11
        and manifest["roles"]["train"] + manifest["roles"]["laya_temperature_holdout"] == 11
    )


def test_verify_export_rejects_a_changed_items_file(fixture_export: Path):
    items = fixture_export / "items.jsonl"
    items.write_text(items.read_text().replace("transferencia", "transferencía"))
    with pytest.raises(AssertionError, match="items.jsonl changed"):
        verify_namespace()["verify_export"](str(fixture_export))


def test_verify_export_rejects_a_failed_guard_in_the_manifest(fixture_export: Path):
    manifest_path = fixture_export / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["leakage_guard"][0]["passed"] = False
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(AssertionError, match="leakage guard did not pass"):
        verify_namespace()["verify_export"](str(fixture_export))


def test_verify_export_rejects_questions_the_manifest_does_not_name(fixture_export: Path):
    manifest_path = fixture_export / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["question_schema_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(AssertionError, match="not the ones the manifest names"):
        verify_namespace()["verify_export"](str(fixture_export))


def test_the_assembled_run_record_validates_against_the_real_schema(fixture_export: Path):
    namespace = {"__name__": "test"}
    exec(marked("assemble-run-record"), namespace)
    manifest = json.loads((fixture_export / "manifest.json").read_text())
    base = load_registry().get("base")
    log = {
        "loss_mode": "full",
        "epochs": 4,
        "loss_per_epoch": [0.9, 0.6, 0.4, 0.3],
        "wall_time_seconds": 300.0,
        "train_fit": {"needs_human": 0.99, "workflow_area": 0.97},
        "laya_temperatures": {"choice": 1.1, "score": 1.2, "noul": 1.2},
        "parameter_count": 322_000_000,
        "train_items_used": 8,
        "holdout_items": 2,
        "settings": {
            "micro_batch": 8,
            "grad_accum": 4,
            "group_size": 4,
            "lr_encoder": 2.5e-5,
            "lr_head": 1e-4,
            "weight_decay": 0.01,
            "schedule": "cosine",
            "min_lr": 1e-6,
            "grad_clip": 1.0,
            "seed": 42,
            "cross_entropy_weight": 1.0,
            "sigma_start": 0.4,
            "sigma_end": 0.1,
            "reward_weight_spherical": 0.75,
            "reward_weight_rps": 1.0,
            "max_len": 1024,
            "head_max_len": 256,
            "max_tokens_per_batch": 4096,
            "gradient_checkpointing": True,
            "mixed_precision": "fp16",
            "torch_seed_base": 42,
            "holdout_max_items": 400,
            "holdout_fraction_percent": 10,
        },
    }
    record = namespace["assemble_run_record"](
        run_number=1,
        run_date="2026-10-20",
        notebook="notebooks/t202_laya_finetune_kaggle.ipynb",
        base={
            "repo": base.repo,
            "subfolder": base.subfolder,
            "revision": base.revision,
            "sha256": base.sha256,
        },
        output={
            "repo": "kevago/calvino-laya-ft",
            "revision": "3" * 40,
            "tag": "t202-run1",
            "sha256": "4" * 64,
        },
        environment={
            "laya_version": "0.3.24",
            "torch_version": "2.2.2",
            "transformers_version": "4.57.6",
            "cuda_version": "12.1",
            "gpu_model": "Tesla T4",
            "gpu_count": 2,
        },
        manifest=manifest,
        log=log,
        deviations=[],
        notes="synthetic test",
    )
    validated = FineTuneRunRecord.model_validate(record)
    assert validated.configuration.effective_batch == 64
    assert validated.configuration.loop.loss == "policy gradient + soft cross-entropy"


def test_the_licence_notice_credits_the_vendor_and_the_apache_licence():
    notice = (NOTEBOOK.parent / "NOTICE.md").read_text(encoding="utf-8")
    for expected in ("NandhaKishorM/laya", "Apache License, Version 2.0", "6ea584941d", "MIT"):
        assert expected in notice


def test_a_verbatim_apache_licence_ships_beside_the_adapted_notebook():
    import hashlib

    licence = NOTEBOOK.parent / "LICENSE-APACHE-2.0.txt"
    text = licence.read_text(encoding="utf-8")
    assert "Apache License" in text and "Version 2.0, January 2004" in text
    assert "END OF TERMS AND CONDITIONS" in text
    notice = (NOTEBOOK.parent / "NOTICE.md").read_text(encoding="utf-8")
    assert hashlib.sha256(licence.read_bytes()).hexdigest() in notice  # the copy is the one named
