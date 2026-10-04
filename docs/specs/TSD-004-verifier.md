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

## Amendment: rubric v2 and fail-closed tiers (decision 40)

- **Rubric v2.** `rubrics/customer-answer-v2.yaml` is the default; v1 stays for replay. The two
  criteria v1 gave to the Laya tier move: `no-money-movement-promise` is a code check (forward-looking
  forms such as the future tense, "will be" and "recibirá su reembolso", plus explicit guarantees;
  "el monto fue reembolsado" is a fact about a Reversed payment and passes, a negated mention
  passes) and
  `factual-claims-grounded` is the judge's. The Laya interface and `FakeLayaChecker` stay for a
  later rubric version that builds a real checker.
- **No silent stand-ins.** `Verifier` no longer defaults a missing judge or Laya checker to a fake.
  A tier with criteria and no implementation returns failed verdicts whose reason starts with
  `unverified`. The keyless demo passes `NotRunJudge`, whose verdicts pass with the reason
  `not run: keyless demo, template reply`.
- **Reply-wording observation.** The end-to-end evaluation independently scans each served reply
  (promise, action claimed without a write, another customer's identifiers) so the report shows
  whether the control held; see TSD-013's unsafe checks.
- **Still open.** The patterns are literal and Spanish-first (Portuguese action claims are not
  covered yet); a paraphrased promise is the judge's job.
