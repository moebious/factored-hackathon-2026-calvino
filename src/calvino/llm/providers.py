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


class ObservedCatalogue(BaseModel):
    """What a provider served on one date, as far as it matters for a drift check."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    date: date
    role: Literal["agent", "judge"]
    source: str = Field(min_length=1)
    ids: tuple[str, ...] = Field(min_length=1)
    served_count: int | None = Field(default=None, ge=1)


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
        if configured and configured != role.model:
            problems.append(
                f"{MODEL_ENV_VAR[name]}={configured} but {providers.version} records "
                f"{role.model} for the {name} role"
            )
        configured_url = values.get(BASE_URL_ENV_VAR[name], "").strip()
        if configured_url and configured_url.rstrip("/") != role.base_url.rstrip("/"):
            problems.append(
                f"{BASE_URL_ENV_VAR[name]}={configured_url} but {providers.version} records "
                f"{role.base_url} for the {name} role"
            )
    return tuple(problems)
