# TSD-002: MCP tools and ISO 20022-aligned contracts

| | |
|---|---|
| Status | draft |
| Branch | `feat/mcp-tools` |
| Depends on | TSD-000 |
| Required by | the Calvino hub and agents (Wave 2–3) |
| Requirements | PRD FR-1, FR-4, FR-5; AC-5, AC-6 |
| Design | DESIGN.md 4.0 (integration spokes), 5.2, 8.2; decisions 9 and 12 |

## Purpose

The MCP server that is Calvino's only path to bank data and actions. Access checks live here, outside any model.

## Interfaces and data models

**Tool contracts** as JSON Schema in `contracts/tools/`, using ISO 20022-aligned shapes ("aligned", not "compliant"). Each field documents its ISO 20022 element.

| Shape | Modelled on | Key fields |
|---|---|---|
| Account entry | camt.053 / camt.054 entry | amount and currency (ISO 4217), credit/debit indicator, booking date, value date, bank transaction code, remittance information, entry reference, status |
| Payment status | pacs.002 | original reference, status, reason |
| Investigation | camt.027 / camt.029 | case id, related entry, reason, status, resolution |

Codes: ISO 4217 (currency), ISO 3166 (country), ISO 18245 (merchant category).

**Adapter protocol:** `BankAdapter` with one method per tool. First implementation: a dataset adapter backed by a small fixture in `tests/fixtures/bank/`, clearly labelled synthetic (a few customers and accounts, normal entries, a pending payment, a reversed payment, a duplicate charge).

**Tools** (workflow-agnostic; the workflow is chosen later):

| Tool | Kind |
|---|---|
| `get_customer_summary` | read |
| `list_accounts` | read |
| `get_account_entries` | read |
| `get_entry_detail` | read |
| `get_payment_status` | read |
| `open_investigation` | write: idempotency key, requires a confirmation token issued by the hub |

## Behaviour

- The session is attached by the hub out-of-band, never as a model-visible argument.
- Every tool checks that the requested record belongs to the session's customer and refuses otherwise, naming the rule.
- Write tools are idempotent; repeating a request with the same key returns the first result.
- Built with the official MCP Python SDK.

## Tests and acceptance

- **Adapter conformance suite**, parametrized over adapters, that every future adapter must pass: schema validity, ownership checks, error codes, idempotency.
- Security: customer A requesting customer B's data, an expired session, a missing record, a duplicate write.

**Done when** the conformance suite and the security tests pass for the dataset adapter.
