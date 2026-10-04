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

**Goal.** Prove corrected and late records cannot silently contaminate the governed offline learning loop (decision 34), while demonstrating update correctness on static data.

**Inputs.** the contracts and partitioning by `process_date`

**Outputs.** a labelled synthetic fixture with late and corrected records; lineage from source version through affected partitions, derived labels and candidate-promotion evidence; tests that rebuild affected outputs and invalidate stale ones while keeping the frozen held-out set isolated

**Open parameters.** none

**Done when.** tests show exactly which labels and candidate evidence change after a correction, no old artifact is silently reused, the frozen evaluation set is not retrained on, and the handling rule is described in DESIGN.md 8.2. This is an offline fixture, not a claim of continuous production ingestion.

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
