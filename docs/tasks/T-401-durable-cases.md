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

**Goal.** A case pauses for a person, survives a restart, and resumes.

**Inputs.** the hub's checkpointer and interrupts; the persistent storage from TSD-003

**Outputs.** a persistent checkpointer and a scripted restart demo

**Open parameters.** none

**Done when.** a case approved after a restart resumes with full state

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
