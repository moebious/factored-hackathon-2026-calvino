# TSD-033: Fairness and Counterfactual Evaluation (T-405)

| | |
|---|---|
| Status | implemented |
| Branch | `feat/fairness-tests` |
| Task | [T-405](../tasks/T-405-fairness-tests.md) |
| Depends on | TSD-013 (Evaluation harness), TSD-032 (Portuguese test set) |
| Required by | T-407 (Flywheel turn), T-408 (Policy replay), T-501 (README results) |
| Requirements | PRD FR-11, FR-12; BRD 3; AC-1, AC-4, AC-8 |
| Design | DESIGN.md 5.1; decisions 22, 25, 33, 37 |

## Purpose

Measure fact-invariant dialect and language routing differences as core empirical evidence for Calvino's bilingual parity, without claiming underpowered groups have passed a binary fairness gate. 

This specification defines the metrics, data models, flip categorization, and reporting tooling for paired counterfactual fairness analysis across the 150 Spanish/Portuguese held-out evaluation pairs from T-203/TSD-032. It cleanly separates **System 1 model-score differences** from **System 1.5 policy-threshold and hard-rule effects**, disclosing the customer impact of each.

## Background & Fairness Principles

1. **Fact-Invariant Counterfactual Consistency (Decision 37, DESIGN 5.1)**:
   In financial workflows, routing differences between demographic or language groups often reflect differences in underlying financial facts (e.g. distinct transaction amounts, currencies, or fraud flags). To isolate purely linguistic variance, Calvino tests 150 strictly paired counterfactual cases:
   - Identical customer persona, accounts, currencies (MXN, COP, ARS, USD), and transaction records.
   - Identical underlying customer intent and oracle expectation (`OracleFacts`).
   - Only the message text varies across Spanish and three Portuguese linguistic variants (Standard PT, Colloquial/Direct PT, Formal/European PT).

2. **Separation of Model Bias and Documented Policy**:
   A verdict flip between Spanish and Portuguese can stem from two distinct mechanisms:
   - **Model Classification Divergence**: System 1 assigns divergent probabilities (e.g. `workflow_area`, `injection`, `talk_to_person`) to semantically identical requests.
   - **Policy & Hard Rule Thresholds**: System 1.5 policy checks (such as route confidence floors, human escalation hard rules, or language-specific margins) fire differently based on calibrated scores.
   Flips caused by policy must be reported with their explicit customer impact (e.g., additional clarification vs. unnecessary escalation), rather than conflated with raw model bias.

3. **Statistical Honesty & Power Constraints (Decision 25)**:
   Any demographic slice or intent subgroup with $n < 30$ cases is explicitly flagged as **statistically inconclusive**. Calvino never claims "binary fairness certification" on underpowered slices. Hypothesis thresholds (e.g. error rate gap $< 5$ pp, flip rate $< 2\%$) remain empirical benchmarks, not automatic release gates.

## Metrics Specification

The fairness evaluator computes four distinct categories of metrics:

### 1. Counterfactual Parity & Flip Rates
For the set of $N = 150$ counterfactual pairs $(c_{es}, c_{pt})$:
- **Route Parity Rate**: Proportion of pairs where `actual_route(es) == actual_route(pt)`.
- **Outcome Parity Rate**: Proportion of pairs where `outcome(es) == outcome(pt)`.
- **Route Flip Rate**: $1 - \text{Route Parity Rate}$.
- **Outcome Flip Rate**: $1 - \text{Outcome Parity Rate}$.

### 2. Flip Attribution & Root Cause Analysis
Every pair $(c_{es}, c_{pt})$ where `actual_route(es) != actual_route(pt)` is classified into one of three root causes:
1. `model_divergence`: Divergence driven primarily by System 1 scoring difference on the primary question (e.g. `workflow_area` probability gap $> 0.15$ or `talk_to_person` crossing a decision boundary).
2. `rule_disparity`: Divergence driven by deterministic hard rules (e.g. entry reference regex match or human keyword detection).
3. `policy_threshold`: Divergence where model probabilities fall into boundary zones where small score perturbations cross route thresholds (e.g. $P(\text{stuck\_payment}) \in [0.48, 0.52]$ around the $0.50$ floor).

### 3. Conditional Error Parity
Computed separately for Spanish ($n = 50$) and Portuguese ($n = 175$):
- **Outcome Agreement Gap**: $|\text{Agreement}_{es} - \text{Agreement}_{pt}|$.
- **Unnecessary Escalation Rate Gap**: $|\text{UER}_{es} - \text{UER}_{pt}|$.
- **Missed Escalation Rate Gap**: $|\text{MER}_{es} - \text{MER}_{pt}|$.
- **Unsafe Outcome Rate Gap**: Must be $0.0\%$ (zero unsafe outcomes across all groups).

### 4. Group & Subgroup Slices
Stratified metrics across:
- **Linguistic Variant**: Standard PT ($n=50$), Colloquial PT ($n=50$), Formal/EP PT ($n=50$).
- **Customer Country**: Mexico (MX), Colombia (CO), Argentina (AR), United States (US).
- **Workflow Intent**: Explain, Cancel, Retry, Human, Clarify, Adversarial probes.
- Any slice with $n < 30$ is prominently marked with `[inconclusive: n < 30]`.

## Architecture & Interfaces

A dedicated module `calvino.evaluation.fairness` implements the measurement engine:

```python
@dataclass(frozen=True)
class FlipAttribution:
    pair_id: str  # e.g. "AC-1 / PT-001"
    spanish_id: str
    portuguese_id: str
    spanish_route: str
    portuguese_route: str
    spanish_outcome: str
    portuguese_outcome: str
    same_route: bool
    same_outcome: bool
    cause: str  # "model_divergence" | "policy_threshold" | "rule_disparity" | "none"
    score_deltas: dict[str, float]
    summary: str


@dataclass(frozen=True)
class SliceMetric:
    slice_name: str
    group_key: str
    sample_size: int
    outcome_agreement: float
    containment: float
    unnecessary_escalations: int
    missed_escalations: int
    is_conclusive: bool  # sample_size >= 30


@dataclass(frozen=True)
class FairnessReport:
    run_date: str
    git_sha: str
    total_pairs: int
    route_agreement_rate: float
    outcome_agreement_rate: float
    flips: tuple[FlipAttribution, ...]
    slices: tuple[SliceMetric, ...]
    agreement_gap: float
    unnecessary_escalation_gap: float
    missed_escalation_gap: float
    unsafe_gap: float
```

### Analysis Runner: `scripts/measure_fairness.py`

CLI tool to extract and format fairness metrics from an existing Tier-0 JSON evaluation artifact (such as `reports/eval/T-303-2026-10-05-f7ca45b.json`):

```bash
uv run python scripts/measure_fairness.py \
    --eval-report reports/eval/T-303-2026-10-05-f7ca45b.json \
    --out-dir reports/eval/
```

Outputs:
- `reports/eval/T-405-<date>-<git-sha>.md` (Human-readable fairness audit).
- `reports/eval/T-405-<date>-<git-sha>.json` (Structured machine-readable flip data).

## Verification & Acceptance Criteria

1. **Unit Tests**:
   - `tests/calvino/evaluation/test_fairness.py` validates metric calculation, flip attribution logic, and the $n < 30$ sample size guard.
2. **Determinism & Reproducibility**:
   - `scripts/measure_fairness.py` reproduces identical figures when run against the committed T-303 evaluation report.
3. **No Unsafe Disparities**:
   - Both Spanish and Portuguese exhibit 0 unsafe outcomes ($0.0\%$ unsafe gap).
4. **Honest Accounting**:
   - All flips among the 150 pairs are enumerated in the flip table with explicit root cause attribution.
