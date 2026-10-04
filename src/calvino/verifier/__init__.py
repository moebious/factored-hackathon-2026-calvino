"""Verifier cascade (TSD-004): code checks, then Laya, then one batched LLM judge over a versioned
rubric.

Public API:
- Rubric, Criterion, load_rubric: versioned rubrics from rubrics/*.yaml.
- CriterionVerdict, VerificationResult: per-criterion verdicts and the fixed
  aggregation (any failed criterion fails the output).
- Evidence, evidence_from_tool_results: the facts a reply may be compared
  against, collected from this session's tool results.
- CODE_CHECKS, run_code_checks: the deterministic check registry.
- Judge, MockJudge, build_judge_prompt, parse_judge_response: the batched LLM
  judge behind a versioned prompt template.
- OpenAiJudge (in ``calvino.verifier.judge``, imported on demand): the same
  interface over a real provider, so this package needs no provider to import.
- LayaChecker, FakeLayaChecker: the Laya grounding checks behind an interface.
- Verifier, VerificationOutcome: the cascade with one retry, escalation and
  DecisionRecord logging.
"""

from calvino.verifier.cascade import Regenerate, VerificationOutcome, Verifier
from calvino.verifier.code_checks import CODE_CHECKS, run_code_checks
from calvino.verifier.evidence import Evidence, ToolResult, evidence_from_tool_results
from calvino.verifier.judge import (
    JUDGE_PROMPT_VERSION,
    Judge,
    MockJudge,
    build_judge_prompt,
    parse_judge_response,
)
from calvino.verifier.laya_checks import FakeLayaChecker, LayaChecker
from calvino.verifier.rubric import (
    DEFAULT_RUBRIC_PATH,
    V1_RUBRIC_PATH,
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
    "V1_RUBRIC_PATH",
    "JUDGE_PROMPT_VERSION",
    "CheckerKind",
    "Criterion",
    "CriterionVerdict",
    "Evidence",
    "FakeLayaChecker",
    "Judge",
    "LayaChecker",
    "MockJudge",
    "Regenerate",
    "Rubric",
    "Severity",
    "ToolResult",
    "VerificationOutcome",
    "VerificationResult",
    "Verifier",
    "build_judge_prompt",
    "evidence_from_tool_results",
    "load_rubric",
    "parse_judge_response",
    "run_code_checks",
]
