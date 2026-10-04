# T-404: Analytics tab

| | |
|---|---|
| Wave | Future UI; not on the current submission path (decision 37) |
| Branch | `feat/analytics` |
| Depends on | T-303 |
| Blocked by | Tier 0 gate |
| Model | standard model |
| Can run in parallel | yes |
| References | BRD 3; PRD persona: supervisor |

**Goal.** Optional visual exploration after reproducible T-303, T-408 and T-501 reports prove the governance metrics. No supervisor changes a live threshold with a dashboard slider.

**Inputs.** evaluation outputs and the decision log

**Outputs.** automation vs unsafe rate vs human load, cost per resolution, results by language, the threshold frontier

**Open parameters.** none

**Done when.** a measured user need calls for an interactive tab and its charts render from existing, versioned evidence. The metrics and their denominators remain core even if this tab is never built.

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
