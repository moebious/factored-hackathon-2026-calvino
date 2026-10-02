# T-103: Labels, splits and gold-set rubric

| | |
|---|---|
| Wave | 1 |
| Branch | `data/labels-splits` |
| Depends on | T-101 |
| Blocked by | workflow decision |
| Model | strong model or maintainer review (judgment checkpoint) |
| Can run in parallel | no |
| References | DESIGN.md 7; TSD-006 outputs |

**Goal.** Produce leakage-free labels and splits for the classifiers and the start of the human-labelled gold set.

**Inputs.** the chosen workflow; interactions, transcripts, complaints

**Outputs.** label definitions, splits by customer and by time, written leakage rules, the gold-set rubric and the first ~50 gold labels

**Open parameters.** [workflow] which labels (route, needs-a-human, intent options); [data] class balance

**Done when.** splits documented and reproducible; leakage tests pass (no customer in two splits, no future data in training, no derived transcript fields as features)

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
