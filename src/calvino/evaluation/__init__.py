"""End-to-end evaluation (TSD-013): oracle, cases, runner, metrics, report.

The evaluation drives the same ``HubService`` the deployment runs, scores
every turn against a hand-written outcome oracle that is independent of the
policy code (DESIGN 7), and reports safe resolution, containment, escalation
quality, unsafe outcomes, latency and cost per suite. Key-gated parts (judge
validation, the bare-LLM ablation) report ``not run: <blocker>`` instead of
failing when no provider keys are present; the tier0 suite needs neither
keys nor network.
"""

from calvino.evaluation.oracle import (
    AMOUNT_BANDS,
    INTENTS,
    ORACLE_VERSION,
    ExpectedOutcome,
    OracleFacts,
    oracle_outcome,
)

__all__ = [
    "AMOUNT_BANDS",
    "INTENTS",
    "ORACLE_VERSION",
    "ExpectedOutcome",
    "OracleFacts",
    "oracle_outcome",
]
