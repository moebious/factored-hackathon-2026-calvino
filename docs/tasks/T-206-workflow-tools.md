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

**Goal.** Extend the MCP tools and the dataset adapter for the chosen workflow.

**Inputs.** TSD-002 contracts; the chosen workflow; the cleaned layer

**Outputs.** any extra tools, the ISO 20022 field mapping for the dataset adapter, a small demo data sample (labelled)

**Open parameters.** [workflow]

**Done when.** conformance and security suites pass with the new tools

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
