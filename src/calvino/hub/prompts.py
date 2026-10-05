"""The versioned prompt file for the support agent (TSD-016).

The prompts live in ``prompts/support-agent-v1.yaml``, next to the policy and playbook, so a
change is reviewable as data and carries a version into the run header and the decision records.
This module only loads and validates the file and renders its pieces; it never calls a model.
Like the policy, a released prompt file is never edited (a test pins the shipped text's hash).
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

# <repo>/prompts/support-agent-v1.yaml, found from this file (src/calvino/hub/prompts.py).
DEFAULT_PROMPTS_PATH = Path(__file__).resolve().parents[3] / "prompts" / "support-agent-v1.yaml"

# The stages in which the model writes the reply (HubStage values). Clarify, investigate and
# out-of-scope replies are fixed texts or card-driven, so they have no prompt.
PROMPT_STAGES = frozenset({"explain", "act", "follow_up"})


class PromptSet(BaseModel):
    """One released prompt version."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str = Field(min_length=1)
    common: str = Field(min_length=1)
    stages: dict[str, str]
    retry: str = Field(min_length=1)
    language_names: dict[str, str]

    @model_validator(mode="after")
    def _complete(self) -> PromptSet:
        if set(self.stages) != PROMPT_STAGES:
            raise ValueError(f"stages must be exactly {sorted(PROMPT_STAGES)}")
        if "{language_name}" not in self.common:
            raise ValueError("common must name the reply language with {language_name}")
        if "{criteria}" not in self.retry:
            raise ValueError("retry must carry the failed criteria with {criteria}")
        if set(self.language_names) != {"es", "pt"}:
            raise ValueError("language_names must cover es and pt")
        return self

    def system(self, stage: str, language: str) -> str:
        """The system prompt for one stage; an unknown stage or language raises."""
        if stage not in self.stages:
            raise KeyError(f"no prompt for stage {stage!r}")
        language_name = self.language_names[language]
        common = self.common.replace("{language_name}", language_name).strip()
        return f"{common}\n\n{self.stages[stage].strip()}"

    def retry_note(self, criteria: list[str]) -> str:
        """The correction appended to the user message on the verifier's retry."""
        return self.retry.replace("{criteria}", "; ".join(criteria)).strip()


def load_prompts(path: str | Path = DEFAULT_PROMPTS_PATH) -> PromptSet:
    """Read and validate a prompt file; an invalid file raises rather than loading partially."""
    with Path(path).open(encoding="utf-8") as handle:
        return PromptSet.model_validate(yaml.safe_load(handle))
