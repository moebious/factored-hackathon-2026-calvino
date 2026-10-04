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

**Goal.** Back the **existing** stuck-payments MCP tools with the full cleaned tables, preserving their shared ownership, confirmation, eligibility and idempotency checks (decisions 17 and 36).

**Inputs.** TSD-002 contracts; the chosen workflow; the cleaned layer

**Outputs.** a full cleaned-table dataset adapter for the existing TSD-002 tools; documented source-to-contract mappings and lineage; a labelled demo sample with personas covering every Gate outcome. The supplied tables' chance-level links cannot be used to assert that a call or complaint was caused by a particular transaction. T-406 owns the second format; T-604 owns the mock ISO message exchange.

**Constraints.** follow the handling rules in DATA.md: payment status from `transaction_status` only (a null `response_code` is not a failure); `Mexico` mapped to MX like `México`; amounts keep their ISO 4217 currency and are converted to USD only for cross-currency figures; demo personas in MX, CO or AR with MXN, COP, ARS or USD, never BRL

**Open parameters.** the action limits (policy assumptions, set in the policy module)

**Done when.** the existing conformance and security suites pass on the cleaned-table adapter, payments are selected by their actual owner/status without invented cross-table attribution, and outputs retain their source and currency. The full-table implementation is not a claim of access to a live banking core.

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
