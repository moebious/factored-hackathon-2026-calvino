# TSD-001: Policy engine

| | |
|---|---|
| Status | draft |
| Branch | `feat/policy-engine` |
| Depends on | TSD-000 |
| Required by | the Calvino hub (Wave 2) |
| Requirements | PRD FR-2, FR-3, FR-4, FR-11; AC-4, AC-8 |
| Design | DESIGN.md 2 (rule inside System 1.5), 4.1, 4.2, 5 |

## Purpose

System 1.5's deterministic decision logic: turn calibrated scores and facts into verdicts. No model calls.

## Interfaces and data models

**Policy configuration:** one versioned file, `policy/v1.yaml`, validated with pydantic. Thresholds and limits live only here.

**Hard rules**, each with a stable id, evaluated before any score is considered and always winning:

| Rule id | Triggers on |
|---|---|
| `HR-FRAUD` | a fraud signal in the facts |
| `HR-AMOUNT` | an amount above the configured limit |
| `HR-ASKS-HUMAN` | an explicit request for a person |
| `HR-AUTH` | repeated authentication failures |
| `HR-REGULATOR` | a complaint received through a regulator |
| `HR-VULNERABLE` | a vulnerable-customer signal |

**Functions** (in `calvino.policy`):

- `decide_route(scores, facts, policy) -> RouteDecision` with `route: Route`, `human_action: HumanAction`, `rule_id`, `record: DecisionRecord`. Two thresholds per decision: act above the upper one, clarify between them, escalate below the lower one; plus the `out_of_scope` outcome.
- `decide_gate(action, scores, facts, policy) -> GateDecision` with `verdict: GateVerdict`, `rule_id`, `record`. Missing inputs fail closed (`block`, or `ask` where policy allows).

## Behaviour

- Hard rules first; the first matching rule decides and is named in the record.
- Thresholds are compared on calibrated probabilities only; never on `action.act_probability`.
- Every call returns and logs a `DecisionRecord` with the rule or thresholds that produced it and the policy version.

## Tests and acceptance

- Each hard rule fires and wins over any score.
- Every threshold boundary (just above, on, just below).
- Missing or malformed inputs fail closed.
- Replay: the same inputs and policy version always give the same verdict (AC-8).

**Done when** the package is fully unit-tested, and DESIGN.md is updated if anything differs from the design.
