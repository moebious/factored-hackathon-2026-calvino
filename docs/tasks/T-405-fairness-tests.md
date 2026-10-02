# T-405: Fairness and counterfactual tests

| | |
|---|---|
| Wave | 4 |
| Branch | `eval/fairness` |
| Depends on | T-303, T-203 |
| Blocked by | Tier 0 gate |
| Model | standard model |
| Can run in parallel | yes |
| References | DESIGN.md 5.1 |

**Goal.** Measure fairness by language, dialect, country and segment.

**Inputs.** held-out sets, paired ES / PT cases

**Outputs.** error gaps, calibration per group, counterfactual flip rates

**Open parameters.** none

**Done when.** results with sample sizes and any disparity investigated

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
