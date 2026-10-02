# T-403: Coworker agent

| | |
|---|---|
| Wave | 4 |
| Branch | `feat/coworker` |
| Depends on | T-302 |
| Blocked by | Tier 0 gate |
| Model | standard model |
| Can run in parallel | yes |
| References | decision 15 |

**Goal.** An agent that prepares cases in the queue for operators.

**Inputs.** the case file; the tools

**Outputs.** case summaries and proposed actions for human approval

**Open parameters.** none

**Done when.** operators see a complete, verified case file prepared by the coworker

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
