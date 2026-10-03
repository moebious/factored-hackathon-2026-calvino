"""Verifier cascade (TSD-004): code checks, then Laya, then one batched LLM judge over a versioned
rubric.

Public API:
- Rubric, Criterion, load_rubric: versioned rubrics from rubrics/*.yaml.
- CriterionVerdict, VerificationResult: per-criterion verdicts and the fixed
  aggregation (any failed criterion fails the output).
- Evidence, evidence_from_tool_results: the facts a reply may be compared
  against, collected from this session's tool results.
- CODE_CHECKS, run_code_checks: the deterministic check registry.
"""

from calvino.verifier.code_checks import CODE_CHECKS, run_code_checks
from calvino.verifier.evidence import Evidence, ToolResult, evidence_from_tool_results
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
    "CODE_CHECKS",
    "DEFAULT_RUBRIC_PATH",
    "CheckerKind",
    "Criterion",
    "CriterionVerdict",
    "Evidence",
    "Rubric",
    "Severity",
    "ToolResult",
    "VerificationResult",
    "evidence_from_tool_results",
    "load_rubric",
    "run_code_checks",
]
