# T-601: AG-UI endpoint and CopilotKit console

| | |
|---|---|
| Wave | Future integration; not on the current submission path (decision 37) |
| Branch | `feat/ag-ui` |
| Depends on | Tier 1 gate |
| Blocked by | — |
| Model | standard model |
| Can run in parallel | yes |
| References | decision 11 |

**Goal.** Optionally plug Calvino into AG-UI after the existing Next.js fixed-card app and MCP/ISO bank boundary are demonstrated. A second console is not required for governed banking decisions.

**Inputs.** the hub

**Outputs.** an AG-UI endpoint and a CopilotKit-based console

**Open parameters.** none

**Done when.** a real integration need warrants a second UI protocol and its console works against the same policy and verified hub outcomes, without letting an agent generate arbitrary action UI.

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
