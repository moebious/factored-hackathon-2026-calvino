# T-302: Handoff queue and audit timeline

| | |
|---|---|
| Wave | 3 |
| Branch | `feat/console-queue` |
| Depends on | T-204 |
| Blocked by | — |
| Model | standard model |
| Can run in parallel | yes |
| References | decision 11; PRD FR-9, FR-10 |

**Goal.** The operator side: cases that need a person, with everything they need.

**Inputs.** the case file and decision log

**Outputs.** a queue view, a case view (verified facts, actions, evidence, open questions), approve / edit / take over through the Gate, an audit timeline naming the rule on every refusal

**Open parameters.** none

**Done when.** PRD UC-6 and AC-4 demonstrated

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
