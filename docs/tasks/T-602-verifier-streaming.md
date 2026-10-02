# T-602: Live verifier streaming

| | |
|---|---|
| Wave | Tier 2 |
| Branch | `feat/verifier-stream` |
| Depends on | T-601 |
| Blocked by | — |
| Model | standard model |
| Can run in parallel | yes |
| References | DESIGN.md 4.4 |

**Goal.** Stream verifier verdicts as they happen.

**Inputs.** the verifier and AG-UI endpoint

**Outputs.** per-criterion events rendered live

**Open parameters.** none

**Done when.** the checklist ticks live in the UI

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
