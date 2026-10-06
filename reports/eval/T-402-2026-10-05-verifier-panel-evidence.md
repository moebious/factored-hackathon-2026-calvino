# T-402: Risk-Tiered Pre-Execution Verifier Panel Evaluation Evidence

- **Task**: T-402 (Verifier Panel Matched-Case Comparison)
- **Specification**: TSD-033
- **Date**: 2026-10-05
- **Evaluated Cases**: 30 matched cases (15 safe, 15 unsafe/corrupted)

## Executive Summary

Decision 35 established that specialist verifiers operate **before execution** with **asymmetric veto-only authority** on otherwise-allowed candidate write actions (`request_cancellation`, `retry_payment`).

This benchmark proves that while the standard output cascade inspects the natural language text, it cannot detect transactional context violations (duplicate action in session history, status ineligibility, or exact database amounts). The pre-execution verifier panel intercepts **100% of unsafe candidate actions** with **0% false fails on legitimate actions** and negligible latency overhead (0.29 ms).

## Comparative Metric Matrix

| Metric | Cascade Alone (Status Quo) | Cascade + Verifier Panel (T-402) | Delta |
|---|---|---|---|
| **Unsafe Intercepted** | 9 / 15 | 15 / 15 | **+6** |
| **False-Pass Rate (FP)** | 40.0% | 0.0% | **-40.0%** |
| **False-Fail Rate (FF)** | 0.0% | 0.0% | **0.0%** |
| **Mean Latency** | 1.36 ms | 1.66 ms | **+0.29 ms** |

## Domain Specialist Failure Breakdown

The 15 unsafe candidates triggered violations across all four domain specialists:
- **Transaction Integrity Specialist (`spec-tx-integrity`)**:
  - `tx-amount-matches-record`: 3 violations (amount discrepancy).
  - `tx-status-eligible`: 3 violations (ineligible status).
- **Policy & Compliance Specialist (`spec-policy-limits`)**:
  - `policy-velocity-bounds`: 3 violations (duplicate action in session).
- **Privacy & Security Specialist (`spec-privacy-guard`)**:
  - `privacy-no-cross-account-leakage`: 3 violations (unauthorized account).
- **Commitment Specialist (`spec-no-unauthorized-promise`)**:
  - `commitment-no-money-movement-guarantee`: 3 violations (unauthorized promise).

## Verification Artifacts
- Machine-Readable JSON Evidence: `reports/eval/T-402-2026-10-05-verifier-panel-evidence.json`
- Unit Test Coverage: `tests/calvino/verifier/test_panel.py` (11 tests passing)
