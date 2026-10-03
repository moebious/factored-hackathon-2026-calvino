# TSD-004: Verifier framework

| | |
|---|---|
| Status | implemented |
| Branch | `feat/verifier` |
| Depends on | TSD-000 |
| Required by | the Calvino hub (Wave 2) |
| Requirements | PRD FR-6, FR-11; AC-7 |
| Design | DESIGN.md 2 (containing System 2), 4.4; decision 14 |

## Purpose

System 2's verification: check every agent output against a rubric before the customer sees it. Built without real model calls; the real judge is plugged in later behind the same interface.

## Interfaces and data models

**Rubrics:** versioned YAML files in `rubrics/`:

```yaml
id: customer-answer
version: 1
output_type: customer_answer
criteria:
  - id: amounts-match
    text: Every amount, date and merchant stated matches a tool result
    checker: code        # code | laya | judge
    severity: blocking
```

The first rubric, `customer-answer`, follows the criteria table in DESIGN.md 4.4.

**Code checks registry:** amounts and dates match tool results; claimed actions were verified by read-back; no other customer's data; reply language matches the customer's.

**Judge interface:** `judge_batch(output, evidence, criteria) -> list[CriterionVerdict]`, one pass/fail verdict with a short reason per criterion. A versioned prompt template decomposes each criterion into a checklist and fails when unclear. `MockJudge` for tests.

**Laya checks** go through an interface that is faked in tests.

## Behaviour

- Cascade: code checks, then Laya questions, then one batched judge call for the remaining criteria.
- Aggregation is a fixed rule: any failed criterion fails the output; a timeout or error counts as a failure.
- On failure: retry once with the failed criteria as feedback, then escalate with the failed criteria in the case file.
- Every verdict is logged as a `DecisionRecord` with the rubric and prompt versions.

## Workflow context (decision 17)

- The `customer-answer` rubric adds the stuck-payments criteria: the stated status, amount, date and merchant match the tool result; the next step is valid for that status; no promise of a refund, credit or money movement; any claimed action was confirmed by a read-back; no other customer's data; the reply is in the customer's language.
- Every criterion verdict records the checker that decided it (code, Laya or judge), so the end-to-end evaluation (T-303) can measure the false-pass rate per checker against hand labels.
- The LLM provider is not chosen yet: the judge stays behind its interface, with `MockJudge` in tests.

## Tests and acceptance

- Each code check, passing and failing.
- Cascade order: criteria handled by code never reach the judge.
- Aggregation, timeouts and errors counted as failures, retry then escalation (AC-7).

**Done when** the package is fully tested with mocked judges and fakes.
