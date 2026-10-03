"""Verifier cascade (TSD-004): code checks, then Laya, then one batched LLM judge over a versioned
rubric.

Public API:
- Rubric, Criterion, load_rubric: versioned rubrics from rubrics/*.yaml.
- CriterionVerdict, VerificationResult: per-criterion verdicts and the fixed
  aggregation (any failed criterion fails the output).
"""

from calvino.verifier.rubric import (
    DEFAULT_RUBRIC_PATH,
    CheckerKind,
    Criterion,
    Rubric,
    Severity,
    load_rubric,
)
from calvino.verifier.verdicts import CriterionVerdict, VerificationResult

__all__ = [
    "DEFAULT_RUBRIC_PATH",
    "CheckerKind",
    "Criterion",
    "CriterionVerdict",
    "Rubric",
    "Severity",
    "VerificationResult",
    "load_rubric",
]
