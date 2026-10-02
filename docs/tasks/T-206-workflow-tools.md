# T-206: Workflow-specific tools and adapter data

| | |
|---|---|
| Wave | 2 |
| Branch | `feat/workflow-tools` |
| Depends on | T-002, T-101 |
| Blocked by | — |
| Model | standard model |
| Can run in parallel | yes |
| References | TSD-002; decision 12 |

**Goal.** Extend the MCP tools and the dataset adapter for stuck payments (decision 17; DESIGN.md 6.1).

**Inputs.** TSD-002 contracts; the chosen workflow; the cleaned layer

**Outputs.** the tools specified in TSD-002 backed by the full cleaned layer instead of the fixture; the ISO 20022 field mapping for the dataset adapter; a small demo data sample (labelled) with personas that cover every Gate outcome

**Constraints.** follow the handling rules in DATA.md: payment status from `transaction_status` only (a null `response_code` is not a failure); `Mexico` mapped to MX like `México`; amounts keep their ISO 4217 currency and are converted to USD only for cross-currency figures; demo personas in MX, CO or AR with MXN, COP, ARS or USD, never BRL

**Open parameters.** the action limits (policy assumptions, set in the policy module)

**Done when.** conformance and security suites pass with the new tools

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
