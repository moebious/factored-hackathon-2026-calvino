# T-104: Human baseline for the chosen workflow

| | |
|---|---|
| Wave | 1 |
| Branch | `eval/baseline` |
| Depends on | T-101 |
| Blocked by | workflow decision |
| Model | standard model |
| Can run in parallel | yes |
| References | BRD 3 |

**Goal.** Establish the baseline every result is compared against.

**Inputs.** interactions for the chosen workflow's reasons

**Outputs.** first-contact resolution, escalation, follow-up, handle time and (if available) CSAT, overall and by country and segment

**Open parameters.** [workflow]

**Done when.** numbers with counts and denominators in `reports/baseline/`, reproducible from one command

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
