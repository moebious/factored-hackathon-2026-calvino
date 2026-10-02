# T-103: Labels, splits and gold-set rubric

| | |
|---|---|
| Wave | 1 |
| Branch | `data/labels-splits` |
| Depends on | T-101 |
| Blocked by | — |
| Model | strong model or maintainer review (judgment checkpoint) |
| Can run in parallel | no |
| References | DESIGN.md 7; TSD-006 outputs |

**Goal.** Define the classifier labels and their rubric, leakage-free splits, and the start of the human-labelled gold set. Classifier text itself is team-generated in T-106 (decision 16).

**Inputs.** the chosen workflow; interactions and complaints (proxy outcomes for the baseline)

**Outputs.** label definitions, splits by customer and by time, written leakage rules, the gold-set rubric and the first ~50 gold labels

**Open parameters.** class balance; the labels follow Laya's questions in DESIGN.md 6.1

**Done when.** splits documented and reproducible; leakage tests pass (no customer in two splits, no future data in training, dataset transcripts never used as model input)

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
