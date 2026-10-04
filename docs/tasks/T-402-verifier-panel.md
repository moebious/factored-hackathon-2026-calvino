# T-402: Risk-tiered verifier panel

| | |
|---|---|
| Wave | Core thesis experiment (decision 35) |
| Branch | `feat/verifier-panel` |
| Depends on | T-004, T-303 |
| Blocked by | — |
| Model | standard model |
| Can run in parallel | yes |
| References | DESIGN.md 4.4; decisions 14, 21 and 35 |

**Goal.** Test the asymmetric safety value of independent specialist vetoes on **otherwise-allowed candidate writes, before execution**. Decision 35 supersedes decision 21's after-escalation placement, not its prohibition on AI granting permission. Hard rules, ownership, eligibility, policy and typed confirmation remain mandatory and cannot be overridden.

**Inputs.** the existing verifier cascade; hand-labelled high-risk candidate actions and evidence; versioned, testable risk tiers grounded in fields the fixture or cleaned data actually provides. No invented AML/KYC, velocity or cross-border signal, or illustrative threshold, is treated as measured evidence.

**Outputs.** an offline matched-case comparison of existing cascade versus risk-tiered panel, with false passes, false fails, vetoed candidate executions, cost and latency; structured failed-criterion IDs and verified evidence for human handoff. If the measured result warrants a runtime hook, any panel failure blocks the write and escalates; all-pass restores only the policy-authorized path.

**Open parameters.** none

**Done when.** independent hand labels establish whether the panel intercepts unsafe candidates beyond the cascade with counts/denominators and measured cost/latency. A panel that sees only already-escalated cases is not credited with reducing unsafe automated executions. The offline result is not described as a deployed runtime shield unless that hook is implemented and tested.

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
