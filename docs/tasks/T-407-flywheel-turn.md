# T-407: One offline flywheel turn

| | |
|---|---|
| Wave | 3 (Tier 0 for decision 17) |
| Branch | `eval/flywheel` |
| Depends on | T-103, T-105, T-201, T-303, T-408 |
| Blocked by | — |
| Model | standard model |
| Can run in parallel | yes |
| References | DESIGN.md 2 |

**Goal.** Demonstrate one self-healing but **offline and governed** learning turn: System 3 teaches System 1 without a model changing its live weights or policy on its own (decision 34).

**Inputs.** reviewed human decisions and audit lineage, corrected-record handling (T-105), training/development splits and a frozen held-out set; the policy promotion scorecard (T-408). An escalation is a candidate label, not gold until reviewed.

**Outputs.** reproducible offline preparation, deduplication, retraining or recalibration, candidate artifact, independent regression and fairness evidence, replay deltas and a human/compliance sign-off record. The candidate may be rejected; a report of no improvement is a valid result. No automatic production promotion.

**Open parameters.** none

**Done when.** one candidate completes the governed evaluation and approval-or-rejection path with every artifact and version linked, the frozen set untouched by training, corrected inputs accounted for and the measured outcome labelled offline. Do not claim production drift reduction from this fixture.

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
