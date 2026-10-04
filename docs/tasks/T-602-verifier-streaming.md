# T-602: Live verifier streaming

| | |
|---|---|
| Wave | Future UX; not on the current submission path (decision 37) |
| Branch | `feat/verifier-stream` |
| Depends on | T-601 |
| Blocked by | — |
| Model | standard model |
| Can run in parallel | yes |
| References | DESIGN.md 4.4 |

**Goal.** Optional live UX after T-601 has a consumer. Safety depends on the blocking verdict and versioned trace, not on streaming intermediate checks to a customer.

**Inputs.** the verifier and AG-UI endpoint

**Outputs.** per-criterion events rendered live

**Open parameters.** none

**Done when.** a measured UI need exists, the checklist ticks live without exposing hidden fraud rules, and only the final verified verdict releases an answer or action.

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
