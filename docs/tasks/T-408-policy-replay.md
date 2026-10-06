# T-408: Offline policy replay and promotion scorecard

| | |
|---|---|
| Wave | 3 (Tier 0 for decision 17) |
| Branch | `feat/policy-replay` |
| Depends on | T-201, T-303 |
| Blocked by | — |
| Model | standard model |
| Can run in parallel | yes |
| References | decisions 4, 18 and 34; PRD FR-15 |

**Goal.** Show deterministic blast radius and a non-regression recommendation for an immutable candidate policy, with no live rule-toggle console.

**Inputs.** replayable logged policy decisions with their original inputs/scores and policy versions; a candidate policy; independent reviewed labels or oracle outcomes to judge safety. A model-weight change requires separately scored model outputs and is **not** policy-only replay.

**Outputs.** an offline CLI or notebook and JSON/Markdown report: replayable count and exclusions, version identities, matrix of old-to-candidate route/Gate verdict transitions, stable case identifiers for every flip, independent safety and fairness deltas with denominators, and an auditable promote/reject recommendation for human approval. No invented 1,000-case corpus or example rates are assumed.

**Open parameters.** none

**Done when.** unchanged inputs under the same policy replay identically; a candidate policy produces an exact, reproducible flip list and any reviewed unsafe regression is a blocking finding. Failures and missing evidence are reported, not treated as zero unsafe outcomes. The output is an offline promotion artifact, not a live switchboard.

**Specification:** [TSD-034](../specs/TSD-034-policy-replay-and-scorecard.md) (implemented).
