"""Tests for the committed provider record (TSD-009, decision 29).

The committed file is loaded in one test, so a broken record fails the suite; the rest build
their own files in a temp folder.
"""

from __future__ import annotations

import pytest
import yaml
from pydantic import ValidationError

from calvino.llm.errors import LlmConfigurationError, LlmRule
from calvino.llm.providers import (
    DEFAULT_PROVIDERS_PATH,
    ProviderFile,
    configuration_problems,
    load_providers,
)

GOOD = """
version: v1
agent:
  provider: hetzner
  base_url: https://inference.hetzner.com/api/v1
  model: Qwen/Qwen3.6-35B-A3B-FP8
  family: qwen
  pin: provider-id
  alternatives: [Qwen3.8-27B]
judge:
  provider: openrouter
  base_url: https://openrouter.ai/api/v1
  model: deepseek/deepseek-v4-pro-0813
  family: deepseek
  pin: dated-release
observed:
  - date: 2026-10-03
    role: judge
    source: openrouter /api/v1/models [measured]
    ids: [deepseek/deepseek-v4-pro-0813]
"""


def write(tmp_path, text: str):
    path = tmp_path / "providers.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_the_committed_record_is_the_one_decision_28_names():
    providers = load_providers()
    assert providers.version == "v1"
    assert providers.agent.model == "Qwen/Qwen3.6-35B-A3B-FP8"
    assert providers.judge.model == "deepseek/deepseek-v4-pro-0813"
    assert providers.agent.pin == "provider-id"
    assert providers.judge.pin == "dated-release"
    assert DEFAULT_PROVIDERS_PATH.name == "providers.yaml"


def test_the_committed_record_satisfies_the_decision_27_guard():
    # load_providers runs the guard, so a record that failed it could not be read at all.
    providers = load_providers()
    assert providers.agent.family != providers.judge.family


def test_the_committed_record_notes_what_each_provider_served():
    providers = load_providers()
    dates = {str(entry.date): entry.role for entry in providers.observed}
    assert dates == {"2026-07-24": "agent", "2026-10-03": "judge"}
    for entry in providers.observed:
        assert entry.ids, "an observation with no ids cannot detect a drift"


def test_a_record_can_be_read_from_a_path(tmp_path):
    providers = load_providers(write(tmp_path, GOOD))
    assert providers.agent.alternatives == ("Qwen3.8-27B",)


def test_a_judge_from_the_agents_family_cannot_be_recorded(tmp_path):
    text = GOOD.replace("deepseek/deepseek-v4-pro-0813", "Qwen3.8-27B").replace(
        "family: deepseek", "family: qwen"
    )
    with pytest.raises(LlmConfigurationError) as caught:
        load_providers(write(tmp_path, text))
    assert caught.value.rule is LlmRule.SAME_FAMILY


def test_a_family_that_contradicts_the_model_id_is_refused(tmp_path):
    with pytest.raises(LlmConfigurationError) as caught:
        load_providers(write(tmp_path, GOOD.replace("family: qwen", "family: llama")))
    assert "does not match the model id" in str(caught.value)


def test_an_unknown_key_is_refused(tmp_path):
    # extra="forbid", so a typo in the record is a failure rather than a silently ignored key.
    with pytest.raises(ValidationError):
        load_providers(write(tmp_path, GOOD + "\nsomething_else: 1\n"))


def test_an_unknown_pin_kind_is_refused(tmp_path):
    with pytest.raises(ValidationError):
        load_providers(write(tmp_path, GOOD.replace("pin: provider-id", "pin: exact")))


def test_a_deployment_matching_the_record_has_no_problems(tmp_path):
    providers = load_providers(write(tmp_path, GOOD))
    env = {
        "CALVINO_LLM_MODEL": "Qwen/Qwen3.6-35B-A3B-FP8",
        "CALVINO_JUDGE_MODEL": "deepseek/deepseek-v4-pro-0813",
        "CALVINO_JUDGE_BASE_URL": "https://openrouter.ai/api/v1",
    }
    assert configuration_problems(providers, env) == ()


def test_a_deployment_pointing_at_another_model_is_reported(tmp_path):
    providers = load_providers(write(tmp_path, GOOD))
    problems = configuration_problems(providers, {"CALVINO_LLM_MODEL": "Qwen3.8-27B"})
    assert len(problems) == 1
    # The message names the variable, the deployed value and the recorded one, because the fix is
    # always "decide which of these two is right".
    assert "CALVINO_LLM_MODEL" in problems[0]
    assert "Qwen3.8-27B" in problems[0]
    assert "Qwen/Qwen3.6-35B-A3B-FP8" in problems[0]


def test_a_deployment_pointing_at_another_endpoint_is_reported(tmp_path):
    providers = load_providers(write(tmp_path, GOOD))
    problems = configuration_problems(providers, {"CALVINO_JUDGE_BASE_URL": "https://elsewhere/v1"})
    assert "CALVINO_JUDGE_BASE_URL" in problems[0]


def test_a_trailing_slash_is_not_a_drift(tmp_path):
    providers = load_providers(write(tmp_path, GOOD))
    env = {"CALVINO_LLM_BASE_URL": "https://inference.hetzner.com/api/v1/"}
    assert configuration_problems(providers, env) == ()


def test_an_unset_variable_is_not_a_drift(tmp_path):
    # A deployment may run the agent without a judge configured yet.
    providers = load_providers(write(tmp_path, GOOD))
    assert configuration_problems(providers, {}) == ()


def test_an_unknown_role_is_refused():
    providers = ProviderFile.model_validate(yaml.safe_load(GOOD))
    with pytest.raises(LlmConfigurationError):
        providers.role("verifier")
