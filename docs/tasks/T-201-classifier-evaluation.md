# T-201: Classifier evaluation and thresholds

| | |
|---|---|
| Wave | 2 |
| Branch | `eval/classifiers` |
| Depends on | T-005, T-106, T-202 for the final comparison |
| Blocked by | — |
| Model | strong model or maintainer review (judgment checkpoint) |
| Can run in parallel | no |
| References | DESIGN.md 4.3, 5, 7; TSD-005 |

**Goal.** Measure whether specialising open-weight Laya changes banking decisions and choose calibrated thresholds by expected cost (decision 34). Base and calibrated baseline runs may precede T-202, but the final comparison cannot omit it.

**Inputs.** the team-generated message set and its splits (T-106); the Laya client and calibration code

**Outputs.** results for majority, rules, logistic regression, base Laya, calibrated base Laya, and fine-tuned then calibrated Laya on the **same frozen held-out set**; calibration per language, missed-human and unsafe-action error counts with denominators, threshold frontier and chosen operating point. Fine-tuning that fails to beat a simpler baseline is reported, never hidden.

**Open parameters.** the cost assumptions (state them); the decision questions are in DESIGN.md 6.1

**Done when.** every variant and its split/model version is named with sample sizes, calibration and safety-relevant errors on held-out data. Thresholds are chosen without consulting the final test split, then written as a new immutable policy version with a stated cost assumption; Portuguese remains evaluation-only.

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
