# T-403: Coworker agent

| | |
|---|---|
| Wave | Future option; not on the current submission path (decision 37) |
| Branch | `feat/coworker` |
| Depends on | T-302 |
| Blocked by | Tier 0 gate |
| Model | standard model |
| Can run in parallel | yes |
| References | decision 15 |

**Goal.** Reconsider a coworker only if operators demonstrably cannot use T-302's verified case file. A model rewriting the same evidence adds another failure surface without a distinct current safety measurement.

**Inputs.** the case file; the tools

**Outputs.** case summaries and proposed actions for human approval

**Open parameters.** none

**Done when.** future operator research identifies a measurable gap, the coworker is separately verified against the original case evidence, and it never grants or overrides action authority. This is not required for the current submission.

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
