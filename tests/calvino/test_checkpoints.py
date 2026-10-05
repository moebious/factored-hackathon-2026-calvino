"""Tests for pinned checkpoints, classifiers.yaml and LayaClient pinning (TSD-020).

No laya install, network or model: the Router is a fake that records how it was
built, and the laya 0.3.24 Router signature is a recorded copy (checked against the
real package only when that exact version happens to be installed).
"""

import inspect
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from calvino.classifiers import laya as laya_module
from calvino.classifiers.checkpoints import (
    DEFAULT_CLASSIFIERS_PATH,
    CheckpointRef,
    ClassifierRegistry,
    load_registry,
    router_kwargs,
)
from calvino.classifiers.laya import LayaClient, needs_human_question

COMMIT = "7b928d828b7b0e022f929d9bd2e44165aa270148"
DIGEST = "9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204"

# Recorded from laya 0.3.24: the Router.__init__ keyword names (self excluded).
ROUTER_0_3_24_PARAMETERS = {
    "models",
    "device",
    "token",
    "revision",
    "revisions",
    "max_loaded",
    "default",
    "auto_task_detection",
    "standalone_repos",
    "preload",
    "lang_guess",
    "hooks",
    "on_predict_start",
    "on_predict_end",
    "hooks_raise",
    "hooks_concurrent",
    "hooks_timeout",
    "agent_kwargs",
    "sha256_digests",
}


def make_ref(**overrides) -> CheckpointRef:
    fields = {
        "name": "base",
        "repo": "convaiinnovations/laya",
        "subfolder": "multilingual",
        "revision": COMMIT,
        "sha256": DIGEST,
        "laya_version": "0.3.24",
    }
    fields.update(overrides)
    return CheckpointRef(**fields)


# --- CheckpointRef validation ---------------------------------------------------------------


def test_ref_accepts_full_commit_and_digest():
    ref = make_ref()
    assert ref.checkpoint_id == f"base@{COMMIT}"
    assert ref.slot == "multilingual"


@pytest.mark.parametrize(
    "revision", ["main", "v1.0", COMMIT[:7], COMMIT[:39], COMMIT + "0", COMMIT.upper(), ""]
)
def test_ref_refuses_anything_but_a_full_lowercase_commit(revision):
    with pytest.raises(ValidationError, match="40-hex"):
        make_ref(revision=revision)


@pytest.mark.parametrize(
    "digest", [DIGEST.upper(), DIGEST[:63], DIGEST + "0", "sha256:" + DIGEST, ""]
)
def test_ref_refuses_a_malformed_digest(digest):
    with pytest.raises(ValidationError, match="64 lowercase hex"):
        make_ref(sha256=digest)


def test_ref_refuses_unknown_fields_and_unknown_slots():
    with pytest.raises(ValidationError):
        make_ref(branch="main")
    with pytest.raises(ValidationError):
        make_ref(slot="candidate")


def test_ref_refuses_blank_names():
    with pytest.raises(ValidationError, match="blank"):
        make_ref(laya_version=" ")


# --- router_kwargs --------------------------------------------------------------------------


def test_router_kwargs_shape_for_a_bundled_subfolder():
    assert router_kwargs(make_ref()) == {
        "models": {"multilingual": ("convaiinnovations/laya", "multilingual")},
        "revisions": {"multilingual": COMMIT},
        "sha256_digests": {"multilingual": {"model.safetensors": DIGEST}},
    }


def test_router_kwargs_for_a_standalone_repo_has_no_subfolder():
    ref = make_ref(name="candidate", repo="kevago/calvino-laya-ft", subfolder=None)
    assert router_kwargs(ref)["models"] == {"multilingual": "kevago/calvino-laya-ft"}


def test_router_kwargs_use_only_arguments_laya_0_3_24_accepts():
    assert set(router_kwargs(make_ref())) <= ROUTER_0_3_24_PARAMETERS


def test_recorded_signature_matches_the_installed_laya_when_it_is_0_3_24():
    if laya_module._installed_laya_version() != "0.3.24":
        pytest.skip("laya 0.3.24 is not installed")
    from laya import Router

    live = set(inspect.signature(Router.__init__).parameters) - {"self"}
    assert live == ROUTER_0_3_24_PARAMETERS


# --- classifiers.yaml -----------------------------------------------------------------------


def test_committed_registry_validates_and_pins_the_base():
    registry = load_registry()
    base = registry.get()
    assert registry.default == "base" and base.name == "base"
    assert base.revision == COMMIT and base.sha256 == DIGEST
    assert base.laya_version == "0.3.24"


def test_committed_registry_run_records_exist():
    root = DEFAULT_CLASSIFIERS_PATH.parent
    for ref in load_registry().checkpoints.values():
        if ref.run_record is not None:
            assert (root / ref.run_record).is_file(), ref.name


def test_registry_default_must_name_an_entry():
    with pytest.raises(ValidationError, match="not a listed checkpoint"):
        ClassifierRegistry(default="missing", checkpoints={"base": make_ref()})


def test_registry_key_must_match_the_entry_name():
    with pytest.raises(ValidationError, match="does not match"):
        ClassifierRegistry(default="base", checkpoints={"base": make_ref(name="other")})


def test_registry_get_unknown_lists_the_known_names():
    registry = ClassifierRegistry(default="base", checkpoints={"base": make_ref()})
    with pytest.raises(KeyError, match="known: \\['base'\\]"):
        registry.get("nope")


def test_load_registry_reads_a_file(tmp_path: Path):
    path = tmp_path / "classifiers.yaml"
    path.write_text(
        yaml.safe_dump({"default": "base", "checkpoints": {"base": make_ref().model_dump()}})
    )
    assert load_registry(path).get("base").revision == COMMIT


# --- LayaClient pinning ---------------------------------------------------------------------


def test_pinned_client_builds_the_router_with_the_checkpoint(fake_router_factory, monkeypatch):
    built = {}
    router = fake_router_factory(
        {"needs_human": {"human needed": 0.8, "can handle automatically": 0.2}}
    )

    def load_router(**arguments):
        built.update(arguments)
        return router

    monkeypatch.setattr(laya_module, "_load_router", load_router)
    monkeypatch.setattr(laya_module, "_installed_laya_version", lambda: "0.3.24")
    ref = make_ref()

    answers = LayaClient(checkpoint=ref).classify("hola", {"needs_human": needs_human_question()})

    assert built == router_kwargs(ref)
    assert router.preloaded_models == ["multilingual"]
    assert answers[0].checkpoint_id == f"base@{COMMIT}"


def test_a_laya_version_mismatch_raises_at_preload(fake_router_factory, monkeypatch):
    monkeypatch.setattr(laya_module, "_load_router", lambda **_: fake_router_factory())
    monkeypatch.setattr(laya_module, "_installed_laya_version", lambda: "0.3.26")
    client = LayaClient(checkpoint=make_ref())

    with pytest.raises(RuntimeError, match=r"pinned to laya 0\.3\.24 but laya 0\.3\.26"):
        client.preload()
    assert client._router is None


def test_without_a_checkpoint_behaviour_is_unchanged(fake_router_factory, monkeypatch):
    calls = []
    router = fake_router_factory(
        {"needs_human": {"human needed": 0.8, "can handle automatically": 0.2}}
    )
    monkeypatch.setattr(laya_module, "_load_router", lambda: calls.append("built") or router)
    # A version mismatch must not matter when nothing is pinned.
    monkeypatch.setattr(laya_module, "_installed_laya_version", lambda: "0.3.26")

    answers = LayaClient().classify("hola", {"needs_human": needs_human_question()})

    assert calls == ["built"]
    assert answers[0].checkpoint_id is None
