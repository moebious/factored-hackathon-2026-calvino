# T-408: Console policy page with rule-and-replay

| | |
|---|---|
| Wave | 3 (Tier 0 for decision 17) |
| Branch | `feat/policy-replay` |
| Depends on | T-302 |
| Blocked by | — |
| Model | standard model |
| Can run in parallel | yes |
| References | decision 11 |

**Goal.** Show governance live: add a rule, replay a case, see it refused and logged.

**Inputs.** the policy engine and decision log

**Outputs.** a read-only policy view plus a demo rule toggle and replay

**Open parameters.** none

**Done when.** the replayed case is refused with the new rule named

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
