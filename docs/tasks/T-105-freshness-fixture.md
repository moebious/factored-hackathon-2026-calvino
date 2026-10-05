# T-105: Update-correctness fixture

| | |
|---|---|
| Wave | 1 |
| Branch | `feat/freshness-fixture` (`data/` is not an allowed branch type in the push hook; see [TSD-021](../specs/TSD-021-freshness-fixture.md)) |
| Depends on | T-102; T-103 and T-106 interfaces only |
| Blocked by | — |
| Model | standard model |
| Can run in parallel | yes |
| References | [TSD-021](../specs/TSD-021-freshness-fixture.md); DESIGN.md 8.2; decision 34 |

**Goal.** Prove corrected and late records cannot silently contaminate the governed offline learning loop (decision 34), while demonstrating update correctness on static data.

**Inputs.** the contracts and partitioning by `process_date`

**Outputs.** a labelled synthetic fixture with late and corrected records; lineage from source version through affected partitions, derived labels and candidate-promotion evidence; tests that rebuild affected outputs and invalidate stale ones while keeping the frozen held-out set isolated

**Open parameters.** none

**Done when.** tests show exactly which labels and candidate evidence change after a correction, no old artifact is silently reused, the frozen evaluation set is not retrained on, and the handling rule is described in DESIGN.md 8.2. This is an offline fixture, not a claim of continuous production ingestion.

**First step:** review and approve [TSD-021](../specs/TSD-021-freshness-fixture.md) before implementing. T-103 and T-106 are interface-only dependencies; T-407 and T-408 consume the resulting lineage/freshness evidence without having their APIs designed here.
