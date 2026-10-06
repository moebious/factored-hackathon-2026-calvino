# TSD-033: Risk-Tiered Pre-Execution Veto Comparison and Verifier Panel (T-402)

| | |
|---|---|
| Status | proposed |
| Branch | `feat/verifier-panel` |
| Task | [T-402](../tasks/T-402-verifier-panel.md) |
| Depends on | TSD-004 (Verifier framework), TSD-013 (Evaluation harness) |
| Required by | T-303 (E2E evaluation), Core Thesis Experiment |
| Requirements | PRD FR-8, FR-11; AC-6, AC-7, AC-8 |
| Design | DESIGN.md 4.4; decisions 14, 21, 35 |

## Purpose

Test the asymmetric safety value of an independent specialist verifier panel executing **veto-only checks on otherwise-allowed candidate writes before execution**.

Per Decision 35 (superseding Decision 21's post-escalation placement):
- Hard rules, ownership checks, status eligibility, policy limits, and single-use confirmation tokens run first and cannot be overridden.
- The panel runs on policy-authorized (`allow` or human-approved `ask`) candidate write actions (`request_cancellation`, `retry_payment`, `open_investigation`).
- The panel possesses **veto-only authority**: any specialist failure blocks execution and converts the turn into a structured human escalation with explicit criterion failure evidence.
- The panel **never grants authority** or overrides policy/gate blocks.
- This specification provides:
  1. A versioned, testable risk tier and specialist panel model (`calvino.verifier.panel`).
  2. Four domain specialists (Transaction Integrity, Policy & Limits, Privacy & Data Leakage, Tone & Commitment).
  3. Matched-case offline evaluation harness and benchmark script (`scripts/evaluate_verifier_panel.py`).
  4. Empirical measurement of intervention rate, false passes, false fails, cost, and latency.

## Risk-Tiered Candidate Action Model

A candidate write action qualifies for specialist panel review if it belongs to a configured `RiskTier`.

```python
class RiskTier(StrEnum):
    LOW = "low"  # Read-only explanation / clarification (cascade only)
    MEDIUM = "medium"  # Routine status change or standard retry under gate limit
    HIGH = "high"  # Consequential write: cancellation, retry above threshold, or disputed investigation
```

### Risk Tier Derivation

Risk tier is computed deterministically from fields existing in the bank fixture or cleaned table schema (amount, transaction status, retry count):
- `HIGH`:
  - `request_cancellation` for amounts $> \$1,000$ equivalent (or currency equivalent $> 15,000$ MXN / $3,500,000$ COP / $300,000$ ARS).
  - Any action on a `Declined` transaction with multiple prior attempts or system error flags.
  - `open_investigation` on flagged transactions.
- `MEDIUM`:
  - Standard `request_cancellation` or `retry_payment` under the high-risk limit.
- `LOW`:
  - Read-only actions (`get_entry_detail`, `list_customer_entries`, `get_investigation_status`).

## Specialist Verifier Panel Design

The panel executes a battery of independent specialist checkers. Specialists receive the proposed candidate write action, the structured bank evidence, and the customer turn context.

### Specialist Roles & Rubric

1. **Transaction Integrity Specialist (`spec-tx-integrity`)**:
   - `amount-currency-exact`: Verifies target payment amount and currency match bank records exactly to the cent.
   - `status-eligible-for-action`: Verifies status is strictly `Pending` for cancellation, or `Declined` for retry.
   - `destination-account-unmodified`: Verifies recipient details have not been swapped or tampered with.

2. **Policy & Compliance Specialist (`spec-policy-limits`)**:
   - `within-velocity-bounds`: Verifies no duplicate action has been executed for this entry reference in the active session.
   - `no-conflicting-investigation`: Verifies an open investigation does not already exist for the target transaction.

3. **Privacy & Data Security Specialist (`spec-privacy-guard`)**:
   - `customer-ownership-verified`: Verifies the target account/payment strictly belongs to the authenticated customer ID.
   - `no-cross-account-leakage`: Ensures no auxiliary customer IDs or unrelated account numbers are referenced.

4. **Commitment & Undertaking Specialist (`spec-no-unauthorized-promise`)**:
   - `no-binding-money-promise`: Verifies no unbacked reimbursement guarantee or unconditional timeline commitment was made.
   - `provisional-credit-prohibited`: Ensures the agent has not granted or promised provisional credit.

### Decision Rule

The panel uses an immutable deterministic aggregation rule:
$$\text{Verdict} = \begin{cases} \text{PASS} & \text{if } \forall s \in \text{Specialists}, \forall c \in s.\text{criteria}, c.\text{passed} = \text{True} \\ \text{VETO} & \text{if } \exists c \in \bigcup s.\text{criteria}, c.\text{passed} = \text{False} \end{cases}$$

- A timeout or failure in any specialist fails closed as a `VETO`.
- A `VETO` blocks the write tool execution, marks `escalate_reason: PANEL-VETO`, and exports the structured `failed_criteria` to the operator case file.

## Matched-Case Benchmark & Evaluation

To evaluate the asymmetric safety value without confounding variables:
- The benchmark runs matched cases:
  1. **Clean Authorized Candidates**: Valid, legitimate customer requests that passed the Gate.
  2. **Adversarial / Corrupted Candidates**: Injected, ungrounded, or cross-account writes that bypassed naive prompt boundaries but reached execution gating.
- For each candidate case, compare:
  - **Standard Cascade Alone** (Status Quo).
  - **Standard Cascade + Pre-Execution Verifier Panel** (T-402).
- Metrics reported:
  - Intercept / Intervention Rate on unsafe candidates (Recall of safety violations).
  - False-Pass Rate ($\text{FP} / \text{Total Unsafe}$).
  - False-Fail Rate ($\text{FF} / \text{Total Safe}$).
  - Latency impact (p50 / p95 in milliseconds).
  - Incremental token and execution cost.

## Acceptance Criteria

1. **AC-Panel-1 (Deterministic Gating)**: Verifier panel correctly evaluates risk tier and executes all specialist checks in parallel or sequence without shared mutable state.
2. **AC-Panel-2 (Fail-Closed Veto)**: Any single criterion failure in any specialist results in an immediate `VETO` and human escalation.
3. **AC-Panel-3 (Zero Authority Granting)**: The panel cannot approve or authorize any action that was rejected by the Gate or Policy engine.
4. **AC-Panel-4 (Measured Offline Evaluation)**: Matched benchmark evaluates $\ge 30$ candidate cases, producing machine-readable JSON and markdown reports in `reports/eval/` detailing exact false-pass and false-fail rates.
