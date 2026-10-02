# T-402: Risk-tiered verifier panel

| | |
|---|---|
| Wave | 4 |
| Branch | `feat/verifier-panel` |
| Depends on | T-004, T-303 |
| Blocked by | Tier 0 gate |
| Model | standard model |
| Can run in parallel | yes |
| References | DESIGN.md 4.4; decision 14 |

**Goal.** Specialist verifiers judging per criterion for high-risk actions. The panel can only veto (decision 21): it runs on cases the Gate sends to a person, specialists never see each other or debate, a fixed rule combines their verdicts, and all-pass still goes to the person.

**Inputs.** the verifier framework; risk tiers from the policy

**Outputs.** the panel, the risk routing, a comparison of batch vs panel on high-risk cases

**Open parameters.** none

**Done when.** false-pass rate and cost reported for both modes

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
