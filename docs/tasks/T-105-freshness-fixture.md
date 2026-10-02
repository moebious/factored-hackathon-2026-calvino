# T-105: Update-correctness fixture

| | |
|---|---|
| Wave | 1 |
| Branch | `data/freshness-fixture` |
| Depends on | T-102 |
| Blocked by | — |
| Model | standard model |
| Can run in parallel | yes |
| References | DESIGN.md 8.2 |

**Goal.** Demonstrate the freshness policy on static data, as the brief requires.

**Inputs.** the contracts and partitioning by `process_date`

**Outputs.** a labelled synthetic fixture with late and corrected records, and a test that rebuilding affected partitions gives the right result

**Open parameters.** none

**Done when.** the test passes and the policy is described in DESIGN.md 8.2

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
