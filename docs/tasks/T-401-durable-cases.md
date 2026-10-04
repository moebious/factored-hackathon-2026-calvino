# T-401: Durable cases

| | |
|---|---|
| Wave | 3 (Tier 0 for decision 17) |
| Branch | `feat/durable-cases` |
| Depends on | T-204, T-302 |
| Blocked by | — |
| Model | standard model |
| Can run in parallel | yes |
| References | DESIGN.md 6 |

**Goal.** A parked graph turn remains resumable by its case reference after a **process restart**, not just within one in-memory service (decision 37).

**Inputs.** the hub's checkpointer and interrupts; the persistent storage from TSD-003

**Outputs.** persistent, recoverable mapping from case reference to the parked thread and renewed trusted session authority, plus a scripted restart demo. The hub already uses SQLite checkpoints when configured, but its current pending-ref/token registry lives in process memory; a database file alone does not satisfy this ticket. Store no raw session token in model-visible state.

**Open parameters.** none

**Done when.** a case opened and parked before restart can be found by case reference and approved or denied after restart with full verified state, without trusting a customer-supplied identity or running an action twice. Broader case-management and long-term retention remain production work.

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
