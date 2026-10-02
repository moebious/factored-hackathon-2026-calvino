# T-406: Second MCP adapter and swap demo

| | |
|---|---|
| Wave | 4 |
| Branch | `feat/second-adapter` |
| Depends on | T-206 |
| Blocked by | Tier 0 gate |
| Model | standard model |
| Can run in parallel | yes |
| References | decision 9 |

**Goal.** Prove the hub is decoupled from the bank core.

**Inputs.** the adapter protocol and conformance suite

**Outputs.** a small adapter with a different internal format mapped to the same contracts

**Open parameters.** none

**Done when.** conformance suite passes; the demo switches adapters with no hub change

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
