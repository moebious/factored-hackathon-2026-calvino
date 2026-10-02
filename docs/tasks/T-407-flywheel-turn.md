# T-407: One offline flywheel turn

| | |
|---|---|
| Wave | 3 (Tier 0 for decision 17) |
| Branch | `eval/flywheel` |
| Depends on | T-201, T-303 |
| Blocked by | — |
| Model | standard model |
| Can run in parallel | yes |
| References | DESIGN.md 2 |

**Goal.** Show System 3 teaching System 1.

**Inputs.** human-confirmed labels; the frozen held-out set

**Outputs.** recalibration from human labels and the measured change on the frozen set

**Open parameters.** none

**Done when.** result labelled offline, with the safeguards applied

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
