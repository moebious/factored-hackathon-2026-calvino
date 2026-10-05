"""The committed record of which models the language work uses (TSD-009, decision 29).

``providers.yaml`` at the repository root says which model answers each role, which provider
serves it, whether the id is a real version pin, and what was served on the date it was checked.
It exists so the choice is a diff somebody reads rather than a value buried in a deployment's
environment, and so a provider quietly re-pointing an id is detectable.

Keys are never in the file. The deployment still sets the model ids in the environment, and
``configuration_problems`` is what catches the two drifting apart.

The family guard from decision 28 runs on load, so the file cannot record an agent and a judge
from the same family.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from calvino.llm.contracts import assert_distinct_families, model_family
from calvino.llm.errors import LlmConfigurationError

# <repo>/providers.yaml, found from this file (src/calvino/llm/providers.py).
DEFAULT_PROVIDERS_PATH = Path(__file__).resolve().parents[3] / "providers.yaml"

PinKind = Literal["provider-id", "dated-release"]

# The environment variable each role's model id is deployed with, so the file and the deployment
# can be compared without a convention nobody remembers.
MODEL_ENV_VAR = {"agent": "CALVINO_LLM_MODEL", "judge": "CALVINO_JUDGE_MODEL"}
BASE_URL_ENV_VAR = {"agent": "CALVINO_LLM_BASE_URL", "judge": "CALVINO_JUDGE_BASE_URL"}


class TokenPrice(BaseModel):
    """USD per million tokens, as the provider publishes them (T-303 prices a run from these)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    input_usd: float = Field(ge=0)
    output_usd: float = Field(ge=0)


class StagingModel(BaseModel):
    """The model a role actually runs today, when that is not the one recorded above.

    A deployment is usually not the destination. The production judge sits behind an account
    nobody has, so the reachable judge is a different family and its numbers describe the
    harness rather than the pinned role. Recording that here keeps the gap legible, instead of
    either hiding it (writing the staging model into ``judge:``) or leaving the file claiming a
    model nobody has called.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str = Field(min_length=1)
    base_url: str = Field(min_length=1)
    model: str = Field(min_length=1)
    family: str = Field(min_length=1)
    measured: date
    note: str = Field(min_length=1)


class RoleModels(BaseModel):
    """One role's provider and model."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str = Field(min_length=1)
    base_url: str = Field(min_length=1)
    model: str = Field(min_length=1)
    family: str = Field(min_length=1)
    # What kind of pin this id is. "provider-id" means the provider publishes no revision, so the
    # id may be re-pointed; "dated-release" means the id names an exact version.
    pin: PinKind
    alternatives: tuple[str, ...] = ()
    # Optional, and never a substitute for the role's recorded model. See StagingModel.
    staging: StagingModel | None = None
    # None while unrecorded: the evaluation then reports tokens as "not priced" instead of $0.
    price_per_million_tokens: TokenPrice | None = None


class ObservedCatalogue(BaseModel):
    """What a provider served on one date, as far as it matters for a drift check."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    date: date
    role: Literal["agent", "judge"]
    source: str = Field(min_length=1)
    ids: tuple[str, ...] = Field(min_length=1)
    served_count: int | None = Field(default=None, ge=1)
    # Recorded for the first live call, so a later reader can see what the provider actually did
    # rather than only which ids it listed.
    # Named for the probe that produced them. A one-word "Reply with exactly: OK" answers in a
    # couple of seconds and is the honest cost of a health check; it is not what the demo sends,
    # and recording it under a bare "latency_ms" invited exactly that reading.
    latency_ms_probe: int | None = Field(default=None, ge=0)
    latency_ms_probe_cold: int | None = Field(default=None, ge=0)
    probe_output_tokens_median: int | None = Field(default=None, ge=0)
    # A real three-sentence reply to a real customer message: the figure to design against.
    draft_latency_ms: int | None = Field(default=None, ge=0)
    draft_output_tokens_median: int | None = Field(default=None, ge=0)
    reasoning_models: bool | None = None
    # Ids that returned nothing within the patience recorded here, as (id, seconds). Deliberately
    # not a verdict: how long we waited says something about our client, not about the model. A
    # DeepSeek id on another provider answered at 273 s, long after this client had given up at
    # 91 s, so "no answer within N seconds" must never be read as "this model is dead".
    no_answer_within_seconds: tuple[tuple[str, float], ...] = ()
    # Judge-routed calls are not drafts, so they get their own fields rather than being forced
    # into the agent's vocabulary. Measured on a real rubric, not on a probe.
    rubric_latency_ms: int | None = Field(default=None, ge=0)
    rubric_latency_ms_full: int | None = Field(default=None, ge=0)


class ProviderFile(BaseModel):
    """The whole record."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str = Field(min_length=1)
    agent: RoleModels
    judge: RoleModels
    observed: tuple[ObservedCatalogue, ...] = ()

    def role(self, name: str) -> RoleModels:
        """The record for one role; ``name`` is "agent" or "judge"."""
        if name not in ("agent", "judge"):
            raise LlmConfigurationError(f"unknown role {name!r}; expected agent or judge")
        return self.agent if name == "agent" else self.judge


def load_providers(path: str | Path = DEFAULT_PROVIDERS_PATH) -> ProviderFile:
    """Read and validate the record; an invalid file raises rather than loading partially."""
    with Path(path).open(encoding="utf-8") as handle:
        providers = ProviderFile.model_validate(yaml.safe_load(handle))
    # The decision 28 guard, run against the committed record instead of the environment, so the
    # file itself cannot encode a judge from the agent's family.
    assert_distinct_families(providers.agent.model, providers.judge.model)
    for name in ("agent", "judge"):
        role = providers.role(name)
        recorded = role.family
        if recorded != model_family(role.model):
            raise LlmConfigurationError(
                f"{name} family {recorded!r} does not match the model id {role.model!r}, "
                f"which reads as {model_family(role.model)!r}"
            )
    return providers


def configuration_problems(
    providers: ProviderFile, env: Mapping[str, str] | None = None
) -> tuple[str, ...]:
    """Compare the deployed ids with the record. Returns one line per problem, empty when clean.

    An unset variable is not a problem: a deployment may configure a role it does not run yet,
    and the live catalogue check is what proves an id is served.
    """
    values = os.environ if env is None else env
    problems: list[str] = []
    for name in ("agent", "judge"):
        role = providers.role(name)
        configured = values.get(MODEL_ENV_VAR[name], "").strip()
        configured_url = values.get(BASE_URL_ENV_VAR[name], "").strip()
        if not configured and not configured_url:
            continue

        # A role may legitimately run its staging model, so that pairing is a valid answer rather
        # than drift. Without this the check fails on every deployment that runs the reachable
        # judge, and a check that always fails stops being read.
        candidates = [(role.model, role.base_url)]
        if role.staging is not None:
            candidates.append((role.staging.model, role.staging.base_url))

        mismatched: list[str] = []
        if configured and not any(configured == model for model, _ in candidates):
            mismatched.append(f"{MODEL_ENV_VAR[name]}={configured}")
        if configured_url and not any(
            configured_url.rstrip("/") == base_url.rstrip("/") for _, base_url in candidates
        ):
            mismatched.append(f"{BASE_URL_ENV_VAR[name]}={configured_url}")
        if mismatched:
            staging_note = f" (staging: {role.staging.model})" if role.staging is not None else ""
            # Name the variable that is actually wrong: the fix is always "decide which of these
            # two is right", and a message about the wrong variable sends the reader elsewhere.
            problems.append(
                f"{'; '.join(mismatched)} but {providers.version} records "
                f"{role.model} on {role.base_url} for the {name} role{staging_note}"
            )
        elif role.staging is not None and configured == role.staging.model:
            # Say it out loud: this deployment is not the recorded one, and the numbers it
            # produces describe a different family than the role pins.
            print(
                f"  note: {name} runs its staging model {configured}, not the recorded "
                f"{role.model}; its numbers describe {role.staging.family}, not "
                f"{role.family}"
            )
    return tuple(problems)
