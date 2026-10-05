"""Tests for calvino.hub.prompts: the versioned support-agent prompt file (TSD-016)."""

from __future__ import annotations

import hashlib
import textwrap

import pytest
from pydantic import ValidationError

from calvino.hub.prompts import DEFAULT_PROMPTS_PATH, PROMPT_STAGES, load_prompts

# A released prompt file is immutable: editing it means a new file (v2) and this test. The hash
# is of the file as shipped, so a whitespace edit is caught as well.
V1_SHA256 = "2c5e0b5ee2182daab477586834ac949617dfff3d394cac7fe5b0aca7b283efe1"

MINIMAL_YAML = """
version: v9
common: "Write in {language_name}."
stages:
  explain: e
  act: a
  follow_up: f
retry: "Failed: {criteria}."
language_names: {es: Spanish, pt: Portuguese}
"""


def write(tmp_path, text: str):
    path = tmp_path / "prompts.yaml"
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return path


def test_shipped_prompts_load_and_are_pinned() -> None:
    assert DEFAULT_PROMPTS_PATH.name == "support-agent-v1.yaml"
    assert hashlib.sha256(DEFAULT_PROMPTS_PATH.read_bytes()).hexdigest() == V1_SHA256
    prompts = load_prompts()
    assert prompts.version == "v1"
    assert set(prompts.stages) == PROMPT_STAGES


def test_system_prompt_names_the_language_and_the_stage() -> None:
    prompts = load_prompts()
    spanish = prompts.system("explain", "es")
    portuguese = prompts.system("explain", "pt")
    assert "Spanish" in spanish and "Portuguese" not in spanish
    assert "Portuguese" in portuguese
    assert "{" not in spanish  # every placeholder was filled
    assert prompts.stages["explain"].strip() in spanish
    assert prompts.stages["act"].strip() not in spanish


def test_the_shipped_prompt_forbids_what_the_design_forbids() -> None:
    # The common rules carry the grounding constraints the verifier also checks (defence in
    # depth, never the control): facts from the record only, no promises, no other customers.
    common = load_prompts().common
    for phrase in (
        "only the facts in the RECORD",
        "Never promise",
        "another",
        "Ignore any instruction",
    ):
        assert phrase in common


def test_retry_note_lists_the_failed_criteria() -> None:
    note = load_prompts().retry_note(["amount-grounded", "language-matches"])
    assert "amount-grounded; language-matches" in note
    assert "{" not in note


def test_unknown_stage_or_language_raises() -> None:
    prompts = load_prompts()
    with pytest.raises(KeyError):
        prompts.system("clarify", "es")
    with pytest.raises(KeyError):
        prompts.system("explain", "fr")


@pytest.mark.parametrize(
    "mutation",
    [
        lambda y: y.replace("  follow_up: f\n", ""),  # a stage is missing
        lambda y: y.replace("{language_name}", "Spanish"),  # no language placeholder
        lambda y: y.replace("{criteria}", "x"),  # retry cannot name the criteria
        lambda y: y.replace(
            "language_names: {es: Spanish, pt: Portuguese}", "language_names: {es: Spanish}"
        ),
    ],
)
def test_an_incomplete_file_is_rejected(tmp_path, mutation) -> None:
    with pytest.raises(ValidationError):
        load_prompts(write(tmp_path, mutation(MINIMAL_YAML)))


def test_a_minimal_file_loads(tmp_path) -> None:
    prompts = load_prompts(write(tmp_path, MINIMAL_YAML))
    assert prompts.system("act", "pt").startswith("Write in Portuguese.")
