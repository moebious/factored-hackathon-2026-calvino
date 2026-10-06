# T-405: Fairness and counterfactual tests

| | |
|---|---|
| Wave | Core thesis evidence (decision 37) |
| Branch | `feat/fairness-tests` |
| Depends on | T-303, T-203 |
| Blocked by | — |
| Model | standard model |
| Can run in parallel | yes |
| References | DESIGN.md 5.1 |

**Goal.** Measure fact-invariant dialect/language routing differences as core evidence, without claiming underpowered groups have passed a binary fairness gate.

**Inputs.** held-out sets, paired ES / PT cases

**Outputs.** paired messages with the same financial facts and request meaning, model-score/calibration comparisons, group-sliced errors and verdict flip rates; a separate table for flips caused by documented stricter Portuguese policy thresholds with their customer impact. Do not call every documented policy difference model bias, and do not conceal its cost.

**Open parameters.** none

**Done when.** results carry pair counts and group denominators, investigate unexplained model-driven flips, flag small groups as inconclusive and report policy-driven ES/PT differences separately. Decision 25's lines remain hypotheses, not automatic promotion gates until the evidence is adequately powered.

**Specification:** [TSD-033](../specs/TSD-033-fairness-and-counterfactuals.md) (proposed).
