# T-206: Workflow-specific tools and adapter data

| | |
|---|---|
| Wave | 2 |
| Branch | `feat/workflow-tools` |
| Depends on | T-002, T-101 |
| Blocked by | workflow decision |
| Model | standard model |
| Can run in parallel | yes |
| References | TSD-002; decision 12 |

**Goal.** Extend the MCP tools and the dataset adapter for stuck payments (decision 17; DESIGN.md 6.1).

**Inputs.** TSD-002 contracts; the chosen workflow; the cleaned layer

**Outputs.** read tools for the customer's problem transactions; the simulated action tool (cancel a pending transfer, retry a declined one) with its eligibility rules, shaped as camt.056 and answered as camt.029; the investigation tools (open a case shaped as camt.027, read its status); the ISO 20022 field mapping for the dataset adapter; a small demo data sample (labelled)

**Open parameters.** the action limits (policy assumptions, set in the policy module)

**Done when.** conformance and security suites pass with the new tools

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
