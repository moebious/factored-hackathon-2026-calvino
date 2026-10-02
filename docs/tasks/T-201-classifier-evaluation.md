# T-201: Classifier evaluation and thresholds

| | |
|---|---|
| Wave | 2 |
| Branch | `eval/classifiers` |
| Depends on | T-005, T-106 |
| Blocked by | — |
| Model | strong model or maintainer review (judgment checkpoint) |
| Can run in parallel | no |
| References | DESIGN.md 4.3, 5, 7; TSD-005 |

**Goal.** Measure System 1 against baselines and choose thresholds by expected cost.

**Inputs.** the team-generated message set and its splits (T-106); the Laya client and calibration code

**Outputs.** results for majority, rules, logistic regression, Laya zero-shot and calibrated (and fine-tuned if available); calibration per language; threshold frontier and chosen operating point

**Open parameters.** the cost assumptions (state them); the decision questions are in DESIGN.md 6.1

**Done when.** results table with sample sizes on held-out data; thresholds written into the policy configuration with their justification

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
