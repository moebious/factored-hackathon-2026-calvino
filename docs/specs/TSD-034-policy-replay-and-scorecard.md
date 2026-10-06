# TSD-034: Offline Policy Replay and Promotion Scorecard (T-408)

| | |
|---|---|
| Status | implemented |
| Branch | `feat/policy-replay` |
| Task | [T-408](../tasks/T-408-policy-replay.md) |
| Depends on | TSD-001 (Policy engine), TSD-013 (Evaluation harness), TSD-030 (Policy v4) |
| Required by | T-407 (Flywheel turn), T-501 (README results) |
| Requirements | PRD FR-11, FR-15; BRD 3; AC-8 |
| Design | DESIGN.md 4.1, 4.2; decisions 4, 18, 30, 34, 44, 46 |

## Purpose

Provide a deterministic offline policy replay engine and an auditable promotion scorecard. This enables governance, compliance, and engineering to evaluate proposed candidate policy configurations against historical decision logs, quantify transition matrices and blast radii, detect regressions against independent oracle labels, and produce an unambiguous `PROMOTE` or `REJECT` recommendation without requiring a live rule-toggle console or unversioned runtime edits.

## Background & Principles

1. **Policy Immutability and Replay Invariant (Decision 18, AC-8)**:
   Every decision made by the system is recorded in the audit log with its exact input facts, model scores, rule id, and policy version. When replaying a `DecisionRecord` under the exact policy version it was recorded with, the verdict and rule firing must match identically:
   $$\text{replay}(\text{record}, \text{record.policy\_version}) \equiv \text{record.verdict}$$
   A regression or deviation on same-policy replay indicates a non-deterministic defect in the policy engine or missing input capture.

2. **Deterministic Blast Radius (Decision 34)**:
   Before any candidate policy is approved, its blast radius must be measured across the entire corpus of historical decision records. The engine computes full old-to-candidate transition matrices for Route decisions (`agents`, `clarify`, `human`, `out_of_scope`) and Gate decisions (`allow`, `ask`, `block`).

3. **Separation of Policy and Model (Decision 34)**:
   Policy replay evaluates changes to System 1.5 logic: hard-rule definitions, threshold parameters, confidence floors, and tie-breaking rules. A change to model weights (System 1) requires separately scored model outputs and is strictly out of scope for policy-only replay.

4. **Zero-Unsafe Promotion Gate**:
   A candidate policy may never be recommended for promotion (`PROMOTE`) if:
   - Same-policy baseline replay deviates on any record.
   - Any case flips from a safe terminal outcome to an unsafe outcome or unverified bypass.
   - Any adversarial case (injection, prompt leak, access bypass) previously caught flips to automated execution.

## Specification

### 1. Data Models (`calvino.policy.scorecard`)

```python
@dataclass(frozen=True)
class VerdictTransition:
    """One verdict transition for a decision record."""

    case_id: str
    decision_id: str
    decision_kind: str  # "route" | "gate"
    baseline_policy: str
    candidate_policy: str
    baseline_verdict: str
    candidate_verdict: str
    baseline_rule_id: str
    candidate_rule_id: str
    is_flip: bool
    customer_impact: str


@dataclass(frozen=True)
class TransitionMatrix:
    """Aggregate matrix of verdict transitions."""

    decision_kind: str
    transitions: dict[tuple[str, str], int]  # (baseline_verdict, candidate_verdict) -> count
    total_records: int
    total_flips: int


@dataclass(frozen=True)
class PromotionScorecard:
    """Auditable policy promotion evaluation scorecard."""

    run_date: str
    git_sha: str
    baseline_policy_path: str
    candidate_policy_path: str
    baseline_policy_version: str
    candidate_policy_version: str
    total_logged_records: int
    replayable_records_count: int
    excluded_records_count: int
    baseline_replay_pass_rate: float  # Must be 1.0 (100%)
    matrices: tuple[TransitionMatrix, ...]
    flips: tuple[VerdictTransition, ...]
    unsafe_regressions_count: int
    recommendation: str  # "PROMOTE" | "REJECT" | "NEEDS_REVIEW"
    recommendation_reasons: tuple[str, ...]
```

### 2. Exclusion Rules

Records in evaluation logs that were not written by the policy engine are explicitly excluded with logged reasons:
- `verifier`: Stage decisions checking LLM drafts (`customer-answer@N`).
- Non-policy stages or records missing `decision_kind` in `inputs_summary`.

### 3. Recommendation Evaluation Rules

The promotion recommendation is determined deterministically:
1. **`REJECT`** if:
   - Baseline replay pass rate $< 1.0$ (AC-8 violation).
   - Any unsafe regression is detected ($> 0$).
   - Any adversarial or security case flips from `human` or `block` to automated route.
2. **`NEEDS_REVIEW`** if:
   - Total flips $> 0$ but zero unsafe regressions, with non-trivial shift in containment or clarification requiring stakeholder approval.
3. **`PROMOTE`** if:
   - Baseline replay pass rate $= 1.0$.
   - Unsafe regressions $= 0$.
   - Unnecessary escalations decrease or remain neutral.
   - Outcome agreement improves or remains non-regressive.

### 4. CLI Interface (`scripts/replay_policy.py`)

```bash
uv run python scripts/replay_policy.py \
    --eval-report reports/eval/T-303-2026-10-05-f7ca45b.json \
    --baseline-policy policy/v3.yaml \
    --candidate-policy policy/v4.yaml \
    --out-dir reports/policy
```

Outputs:
- Markdown report: `reports/policy/T-408-<date>-<sha>.md`
- JSON scorecard: `reports/policy/T-408-<date>-<sha>.json`

## Test Plan

1. **AC-8 Baseline Replay Invariant**:
   - Replaying logged Policy v4 decisions against `policy/v4.yaml` yields 100% agreement on all 236 records.
2. **Deterministic Flip Attribution**:
   - Replaying across known policy iterations ($v1 \to v2 \to v3 \to v4$) yields the exact transition counts and case ids.
3. **Safety Guarding**:
   - Simulated candidate policy with an unsafe regression triggers `REJECT` recommendation.
4. **Exclusion Handling**:
   - Non-policy decision records (verifier stages) are cleanly filtered and accounted for.
