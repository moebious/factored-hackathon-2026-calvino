"""Versioned rubrics (TSD-004): what every agent output is checked against.

A rubric is a YAML file in ``rubrics/`` listing pass/fail criteria, each with
the checker that decides it (code, Laya or judge) and its severity. Like the
policy, a released version is never edited; a change is a new file, so logged
verdicts replay under the rubric version they were made with (decision 14).
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

# <repo>/rubrics/customer-answer-v2.yaml, found from this file (src/calvino/verifier/rubric.py).
# v1 stays in customer-answer.yaml so logged verdicts replay under the rubric they were made with.
DEFAULT_RUBRIC_PATH = Path(__file__).resolve().parents[3] / "rubrics" / "customer-answer-v2.yaml"
V1_RUBRIC_PATH = Path(__file__).resolve().parents[3] / "rubrics" / "customer-answer.yaml"


class CheckerKind(StrEnum):
    """Which checker decides a criterion. The cascade runs them cheapest first."""

    CODE = "code"
    LAYA = "laya"
    JUDGE = "judge"


class Severity(StrEnum):
    """What a failed criterion means for the output.

    Only ``blocking`` exists today (any failed criterion fails the output);
    the enum keeps the field typed for a future advisory level.
    """

    BLOCKING = "blocking"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Criterion(_Frozen):
    """One pass/fail criterion of a rubric."""

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    text: str = Field(min_length=1)
    checker: CheckerKind
    severity: Severity


class Rubric(_Frozen):
    """One versioned rubric for one agent output type."""

    id: str = Field(min_length=1)
    version: int = Field(ge=1)
    output_type: str = Field(min_length=1)
    criteria: list[Criterion] = Field(min_length=1)

    @model_validator(mode="after")
    def _criterion_ids_are_unique(self) -> Rubric:
        ids = [criterion.id for criterion in self.criteria]
        duplicates = {criterion_id for criterion_id in ids if ids.count(criterion_id) > 1}
        if duplicates:
            raise ValueError(f"criterion ids must be unique, got duplicates: {sorted(duplicates)}")
        return self

    @property
    def ref(self) -> str:
        """The reference recorded in ``DecisionRecord.versions.rubric``."""
        return f"{self.id}@{self.version}"

    def criteria_for(self, checker: CheckerKind) -> list[Criterion]:
        """The criteria decided by one checker, in rubric order."""
        return [criterion for criterion in self.criteria if criterion.checker == checker]


def load_rubric(path: str | Path = DEFAULT_RUBRIC_PATH) -> Rubric:
    """Read and validate a rubric file; an invalid file raises rather than loading partially."""
    with Path(path).open(encoding="utf-8") as handle:
        return Rubric.model_validate(yaml.safe_load(handle))
