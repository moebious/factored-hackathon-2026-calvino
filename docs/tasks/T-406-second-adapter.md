# T-406: Second MCP adapter and swap demo

| | |
|---|---|
| Wave | Core adapter-swap proof (decision 36) |
| Branch | `feat/second-adapter` |
| Depends on | T-206 |
| Blocked by | — |
| Model | standard model |
| Can run in parallel | yes |
| References | decision 9 |

**Goal.** Prove the hub and policy are decoupled from a bank adapter's internal format, independently of T-604's ISO message exchange.

**Inputs.** the adapter protocol and conformance suite

**Outputs.** a second synthetic adapter with a genuinely different internal representation mapped to the same governed contracts; identical seeded journey and security checks over both adapters with **no changes** to the hub or policy

**Open parameters.** none

**Done when.** both adapters pass ownership, eligibility, idempotency and conformance tests and the swap changes no hub/policy code or authorized outcomes. This demonstrates format independence, not live bank-core readiness or ISO schema compliance.

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
