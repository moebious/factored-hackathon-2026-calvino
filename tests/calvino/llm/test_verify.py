"""Tests for the catalogue check (TSD-009, decision 29).

Everything runs offline: the served lists are written out by hand, from what the providers
returned on the dates recorded in ``providers.yaml``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from calvino.llm.verify import unrecorded, verify_catalogue

AGENT_MODEL = "Qwen/Qwen3.6-35B-A3B-FP8"
JUDGE_MODEL = "deepseek/deepseek-v4-pro-0813"

# Hetzner's documentation, 2026-07-24 [vendor].
HETZNER_SERVED = (AGENT_MODEL, "Qwen3.8-27B")
# OpenRouter's public /api/v1/models, 2026-10-03 [measured]; the pinned judge and its alternative.
OPENROUTER_SERVED = (JUDGE_MODEL, "deepseek/deepseek-v4-pro", "deepseek/deepseek-chat")


def test_a_served_model_is_not_a_problem():
    assert verify_catalogue(AGENT_MODEL, HETZNER_SERVED, role="agent") == ()
    assert verify_catalogue(JUDGE_MODEL, OPENROUTER_SERVED, role="judge") == ()


def test_a_retired_model_names_what_the_provider_serves():
    problems = verify_catalogue("Qwen3.9-99B", HETZNER_SERVED, role="agent")
    assert "agent: Qwen3.9-99B is not served" in problems[0]
    assert "serves 2 model(s)" in problems[0]
    assert AGENT_MODEL in problems[0]
    # The other model the same provider serves is worth suggesting: if the configured id is
    # retired, that one is where the agent should move.
    assert any("Qwen3.8-27B" in line for line in problems)


def test_a_renamed_model_suggests_the_id_that_exists():
    # The usual cause is a rename, so a re-suffixed id must be suggested even though a closeness
    # ratio would rank it far below the rest.
    problems = verify_catalogue("deepseek/deepseek-v4-pro-0815", OPENROUTER_SERVED, role="judge")
    assert any("did you mean" in line for line in problems)
    assert any("deepseek/deepseek-v4-pro-0813" in line for line in problems)


def test_a_typo_is_suggested():
    problems = verify_catalogue("deepseek/deepseek-v4-pro-081", OPENROUTER_SERVED)
    assert any("deepseek/deepseek-v4-pro-0813" in line for line in problems)


def test_an_empty_catalogue_is_reported_rather_than_raising():
    problems = verify_catalogue(AGENT_MODEL, (), role="agent")
    assert problems == (
        "agent: Qwen/Qwen3.6-35B-A3B-FP8 is not served; the provider serves 0 model(s): none",
    )


def test_an_unrelated_catalogue_gets_no_suggestion():
    # Suggesting the wrong model is worse than suggesting nothing.
    problems = verify_catalogue("some/other-model", ("anthropic/claude-x",))
    assert len(problems) == 1
    assert "did you mean" not in problems[0]


def test_unrelated_ids_served_since_the_snapshot_are_a_note_not_a_failure():
    extra = unrecorded(HETZNER_SERVED, (*HETZNER_SERVED, "Qwen3.9-99B"))
    assert extra == ("Qwen3.9-99B",)
    assert unrecorded(HETZNER_SERVED, HETZNER_SERVED) == ()


@pytest.mark.parametrize("args", [["--help"]])
def test_the_script_runs_offline_in_config_only_mode(args):
    """The command in AGENTS.md must work without a network or a token."""
    env = {
        **os.environ,
        "CALVINO_LLM_MODEL": AGENT_MODEL,
        "CALVINO_JUDGE_MODEL": JUDGE_MODEL,
        "CALVINO_JUDGE_BASE_URL": "https://openrouter.ai/api/v1",
    }
    result = subprocess.run(
        [sys.executable, "scripts/check_providers.py", *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=Path(__file__).resolve().parents[3],
    )
    assert result.returncode == 0, result.stderr
    assert "--config-only" in result.stdout


def test_the_script_fails_on_config_drift():
    env = {**os.environ, "CALVINO_LLM_MODEL": "Qwen3.8-27B"}
    result = subprocess.run(
        [sys.executable, "scripts/check_providers.py", "--config-only"],
        capture_output=True,
        text=True,
        env=env,
        cwd=Path(__file__).resolve().parents[3],
    )
    assert result.returncode == 1
    assert "FAILED" in result.stdout
    assert "Qwen/Qwen3.6-35B-A3B-FP8" in result.stdout


def test_the_script_reports_an_unconfigured_deployment_instead_of_raising():
    env = {key: value for key, value in os.environ.items() if not key.startswith("CALVINO_")}
    result = subprocess.run(
        [sys.executable, "scripts/check_providers.py"],
        capture_output=True,
        text=True,
        env=env,
        cwd=Path(__file__).resolve().parents[3],
    )
    # No keys: the catalogue is skipped, and the missing configuration is the failure.
    assert result.returncode == 1
    assert "not configured" in result.stdout
    assert result.stderr == ""
