# T-103: Labels, splits and gold-set rubric

| | |
|---|---|
| Status | done (implementation; human gold review moved to T-107) |
| Wave | 1 |
| Branch | `data/labels-splits` |
| Depends on | T-101 |
| Blocked by | — |
| Model | strong model or maintainer review (judgment checkpoint) |
| Can run in parallel | no |
| References | DESIGN.md 7; TSD-006 outputs |

**Goal.** Define the classifier labels and their rubric, leakage-free splits, and the schema and tools for the human-labelled gold set. Classifier text itself is team-generated in T-106 (decision 16).

**Inputs.** the chosen workflow; interactions and complaints (proxy outcomes for the baseline)

**Outputs.** label definitions, reproducible customer and time splits, written leakage rules, the gold-set rubric, schema, and blank 50-row annotation worksheet. Human annotation and agreement reporting are tracked in [T-107](T-107-gold-annotation.md).

**Open parameters.** class balance; the labels follow Laya's questions in DESIGN.md 6.1

**Done when.** splits are documented and reproducible; leakage tests pass (no customer in two splits, no future data in training, dataset transcripts never used as model input); rubric, schema, validation and blank worksheet are implemented. The first-50 human annotations are not a T-103 completion gate; T-107 owns that work.

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
