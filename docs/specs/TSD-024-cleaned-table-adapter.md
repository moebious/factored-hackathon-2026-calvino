# TSD-024: Cleaned-table adapter for the stuck-payments tools (T-206)

| | |
|---|---|
| Status | implemented locally; not yet merged |
| Branch | `feat/workflow-tools` |
| Task | [T-206](../tasks/T-206-workflow-tools.md) |
| Depends on | TSD-002 / T-002; TSD-006 / T-101; TSD-007 / T-102 |
| Amends | TSD-002 read-output nullability for source fields that do not exist |
| Design | DESIGN.md 4.0, 5.2, 8.2; decisions 9, 12, 17, 36 |

## Purpose

Back the existing stuck-payments `BankAdapter` with the full cleaned
`customers`, `products`, and `transactions` tables. Keep the existing
`BankTools` ownership, eligibility, confirmation, and idempotency boundary.
This is a read-only data adapter with simulated writes, not a live bank
connection or a replacement MCP contract.

T-103 and T-106 are not dependencies. This work does not train, fine-tune,
calibrate, or evaluate Laya.

## Scope

**In scope**

- Add `CleanedTableAdapter`, implementing the existing `BankAdapter` protocol.
- Query the cleaned Parquet tables through DuckDB without materializing the
  full tables in Python memory.
- Make existing tool response fields nullable only where the documented
  source tables have no corresponding field.
- Preserve transaction ownership and source status, and fail closed when an
  incomplete source row cannot support a write or confirmation.
- Add a small, clearly synthetic fixture and run the existing adapter
  conformance, security, eligibility, and contract suites against it.
- Document the source-to-tool mapping and input lineage.

**Out of scope**

- Reading or writing the organizer's live dataset from tests or CI.
- Re-running the upstream cleaning pipeline or repairing source rows.
- Joining calls or complaints to transactions. Those links are at chance and
  must not be asserted as causal.
- Changing tool names, model-visible session handling, or the hub's workflow.
- A second adapter format (T-406), ISO 20022 middleware (T-604), live core
  access, or any Laya work.

## Inputs and operating boundary

- The maintainer-provided cleaned Parquet layer, selected by explicit table
  paths at startup. The layer is local and git-ignored; the adapter never
  discovers a bucket or reads credentials.
- TSD-007's `Customer`, `Product`, and `Transaction` contracts and their
  error-level rules. Known defects are counted and retained, not cleaned
  away. An error-level validation failure prevents adapter startup.
- A tiny synthetic CSV fixture for tests. Tests need no real data, network,
  or credentials.

Require a successful TSD-007 audit report for the selected cleaned layer
before enabling the adapter. Do not rescan the full layer on every request.
Use DuckDB for parameterized, read-only queries against the selected Parquet
files. Filter customer-owned queries by the `Session.customer_id` attached by
the hub. Do not concatenate model- or caller-supplied values into SQL. Do not
load the full tables into lists or DataFrames. Simulated write effects stay in
the adapter's in-memory action log and case store; the cleaned files remain
unchanged.

List results use a stable order by source primary key. For date-filtered reads,
rows with no source date are excluded when either bound is supplied; unbounded
reads may include them with a null date. Never substitute a processing date
or another event's date.

The adapter consumes only the three tables above because they are the sources
needed by the existing `BankAdapter` methods. It does not claim that the
call-center or complaint tables describe a specific transaction.

## Source-to-tool mapping

| Source | Tool representation | Rule |
|---|---|---|
| `customers.customer_id` | `CustomerSummary.customer_id` and owner checks | Preserve exactly; never accept a customer id from a tool argument to choose the session owner. |
| `customers.country` | `CustomerSummary.country` | Map `México` to `MX`, `Colombia` to `CO`, and `Argentina` to `AR`. Other values fail the TSD-007 preflight; do not create Brazilian customers. |
| `customers.segment` | `CustomerSummary.segment` | Preserve when present; otherwise return `null`. |
| customer display name | `CustomerSummary.display_name` | No documented source field exists; return `null`, never synthesize a name from an id. |
| bank account count | `CustomerSummary.account_count` | Return `null`: `products` rows are not verified cash accounts, so do not derive this count from `products`. |
| `products.product_id` | `Account.account_id` and transaction account association | Preserve as the product/account reference. A transaction with null `product_id` is not attached to an account. |
| `products.product_type` | `Account.account_type` | Preserve when present; otherwise return `null`. |
| `products.currency` | `Account.currency` | Preserve a supported ISO 4217 code; otherwise return `null` only for a source null. Unsupported non-null codes fail the TSD-007 preflight. |
| account balance and account status | `Account.balance` and `Account.status` | These fields are absent from the documented `products` contract. Return `null`; do not derive balances from transactions or assume an account is active. |
| `transactions.transaction_id` | `AccountEntry.entry_reference` | Preserve exactly. |
| `transactions.customer_id` | `EntryRecord.customer_id` and owner checks | This is the ownership source of truth, including when `product_id` is null. |
| `transactions.product_id` | `EntryRecord.account_id` | Preserve when present only if the referenced product belongs to the same `customer_id`. Null means no product relationship can be asserted. |
| `transactions.transaction_status` | `AccountEntry.status` and `PaymentStatus.status` | The sole status source. Ignore `response_code`, including null values. Invalid or missing statuses fail preflight rather than being guessed. |
| status reason | `PaymentStatus.reason` / internal `EntryRecord.status_reason` | No documented source reason exists; return `null`. Never derive it from `response_code`. |
| `transactions.amount` | `AccountEntry.amount` and internal action facts | Preserve only a finite, positive amount representable by the tool contract; otherwise return `null` and record an incomplete-source count. Never take an absolute value or substitute `amount_usd`. |
| `transactions.currency` | `AccountEntry.currency` and internal action facts | Preserve MXN, COP, ARS, or USD. Do not convert the customer-facing transaction amount to USD. |
| `transactions.transaction_date` | `AccountEntry.booking_date` | Preserve the source transaction date's calendar date without claiming a distinct bank booking date. If it includes a time, use its date component without timezone conversion. `value_date` remains `null`, since no separate source value is documented. |
| `transactions.transaction_type` | internal `EntryRecord.transaction_type` | Preserve when present; a missing type cannot authorize cancel or retry. |
| `transactions.is_fraud` | internal `EntryRecord.fraud_flagged` | Preserve `true`, `false`, or `null`. Null is unknown, not “not fraud.” It is never exposed in tool output. |
| no documented direction, bank-code, remittance, or MCC source | `credit_debit`, `bank_transaction_code`, `remittance_information`, `merchant_category_code` | Return `null` unless a separately documented, approved mapping is added. Do not infer ISO codes or remittance text. |
| `transactions.transaction_country` | `AccountEntry.country` | Map recognized source labels to ISO 3166 alpha-2 codes: `Mexico`/`México`→`MX`, `Colombia`→`CO`, `Argentina`→`AR`, `USA`→`US`, `Brazil`→`BR`, and `Spain`→`ES`. Unknown labels return `null` and are counted; transaction country never determines the customer country. |

The existing tool names remain unchanged. In this adapter, each `Account` is a
compatibility projection of a source `Product`, not a claim that the source
contains a cash account, balance, or active account status. Update the tool
and model descriptions to say "linked product"; customer-facing agent and UI
text must use that wording and must not state that a nullable fact is known.
Investigation cases remain adapter-owned simulated cases. Do not adapt
`complaints` rows as cases or assert they concern the selected transaction.

## TSD-002 contract amendment

Keep the existing fields and tool names, but allow absent source facts to be
represented honestly:

- `CustomerSummary.display_name`, `segment`, and `account_count` become
  optional. Return a null `account_count`, because the documented source has
  no bank-account table.
- `Account.account_type`, `currency`, `status`, and `balance` become optional.
- Document `Account.account_id` as the source product id for this adapter.
- `AccountEntry.booking_date`, `value_date`, `amount`, `currency`, `credit_debit`,
  `bank_transaction_code`, `remittance_information`,
  `merchant_category_code`, and `country` become optional.
- Internal `EntryRecord.account_id` and `transaction_type` become optional;
  `fraud_flagged` becomes `bool | None`.
- `transaction_status`, `transaction_id`, and `customer_id` stay required by
  the TSD-007 source contracts.
- Add stable refusal rule `TOOL-SOURCE-INCOMPLETE` for a write whose required
  source facts are missing. `BankTools` uses it when the fraud flag is unknown
  for cancel/retry; a known `true` flag retains `TOOL-FRAUD-FLAGGED`.

Regenerate the JSON Schemas from the models and update the synthetic
`DatasetAdapter`, tool docs, Hub, UI, and tests to the revised nullability.
The `booking_date` field description must say it carries the source
transaction date in this projection, not a separately sourced bank booking
date. Hub and UI consumers must tolerate `null` without displaying fabricated
facts. The hub must check for required action evidence before constructing
`GateAction`; it must not coerce a missing amount to zero.

## Ownership, incomplete data, and writes

- Every lookup by entry or account must establish the session customer's
  ownership before returning data or performing an action. A null
  `product_id` does not erase transaction ownership from
  `transactions.customer_id`.
- When a transaction has a non-null `product_id`, verify that the referenced
  product exists and has the same `customer_id`. A mismatch is a source
  integrity violation: fail preflight, prevent adapter startup, and include
  only the aggregate violation count in the report. Never repair it by
  substituting another customer's product or by trusting one join key alone.
- `get_account_entries` returns only entries with the requested
  `product_id`. An entry without a product association remains available to
  its owner through the customer-scoped problem-transaction list and direct
  entry lookup; it is never attached to a guessed account.
- `get_investigation_status` reads only cases created in this adapter's
  simulated case store. Cleaned complaints are not investigation cases.
- Reads may return rows with nullable display-only fields. The customer UI
  renders those values as unavailable.
- Cancel, retry, and investigation writes require the exact positive amount
  and supported currency used to bind the existing confirmation token. If
  either is missing, `BankTools` refuses with `TOOL-SOURCE-INCOMPLETE` before
  token consumption or action-log mutation, even if a caller bypasses the Hub.
- Cancel and retry additionally require an explicitly known fraud flag of
  `false`, an actionable `transaction_type`, and the existing eligible status.
  `BankTools` refuses a null fraud flag as `TOOL-SOURCE-INCOMPLETE` and a
  `true` flag as `TOOL-FRAUD-FLAGGED`, before consuming the token. Investigation
  remains available for an explicitly flagged transaction when its
  confirmation facts are complete, as TSD-002 specifies.
- If a pending hub write lacks required amount/currency facts, do not call the
  policy with made-up facts or issue a token. Log a fail-closed
  `FC-INCOMPLETE-SOURCE` decision and route to a person. No adapter or hub
  write mutates the cleaned source files.
- Idempotency replay, fraud privacy, and confirmation-token binding remain
  enforced in `BankTools` and the existing verifier. The new adapter must not
  duplicate or bypass those checks.

## Lineage and data handling

- The mapping table above is the source-to-tool contract.
- After all required-table and ownership preflight checks pass, record the
  selected logical table names, TSD-007 contract version, and SHA-256 digests
  of the input files in local run metadata. A failed preflight writes no
  lineage manifest. Record relative logical names only, not absolute paths or
  storage identifiers. Do not serialize source rows into the manifest.
- Reusing a `lineage_path` with an identical manifest is an idempotent no-op.
  Different manifest content is refused; operators must choose a new path for
  each cleaned-data version.
- Create manifests without overwriting existing files. Prefer an atomic
  same-directory hard link from a temporary file. When the filesystem reports
  hard links unsupported, fall back to an exclusive (`x`) write. The fallback
  is not atomic against process termination: a crash mid-write can leave a
  partial manifest that blocks restart. After confirming no writer remains,
  an operator must remove that partial metadata file or use a new path.
- The validator's row counts and known-defect counts remain aggregates.
  Git-tracked outputs contain only the synthetic fixture and its README.
- Use the existing DATA.md rules: no BRL or Brazilian demo customers; retain
  original transaction currencies; normalize `Mexico` to `MX`; and never use
  `response_code` as a payment-status signal.

## Tests and acceptance

1. The existing `tests/calvino/tools/test_conformance.py` runs against both
   `DatasetAdapter` and `CleanedTableAdapter`, including every existing tool
   contract and supported status.
2. The existing security suite proves cross-customer reads and writes are
   refused, missing/expired sessions fail closed, and idempotency and token
   checks are unchanged.
3. The synthetic fixture covers MX, CO, and AR; MXN, COP, ARS, and USD; all
   Gate outcomes; and missing optional fields. It is labelled synthetic.
4. Tests prove null `response_code` never changes transaction status, missing
   fields remain null, native amounts/currencies are preserved, and no
   call/complaint-to-transaction relationship is fabricated.
5. Incomplete source facts allow owner-scoped reads but prevent writes with
   `TOOL-SOURCE-INCOMPLETE` and no side effects. Unknown fraud status never
   authorizes cancel or retry.
6. The adapter opens only the selected cleaned files read-only, filters
   customer queries, leaves files byte-identical, and does not load full tables
   into Python memory.
7. The TSD-007 preflight rejects error-level violations and records known
   defects without silently changing source values; the adapter additionally
   detects transaction/product customer-owner mismatches.
8. Contract schemas are regenerated and match the revised Pydantic models;
   relevant Hub and customer-UI tests cover nullable responses and
   fail-closed Gate behavior.
9. All committed tests use synthetic data only and run offline.

**Done when** all existing conformance, security, eligibility, hub, and
contract-schema checks pass with the adapter registered, the source mapping
and lineage are documented, and the synthetic Gate-outcome personas run
without Laya or live data.

## Implementation boundary

T-206 adapts existing data to existing tools. It does not choose new action
limits, add new tools, assert causal joins, add a live-core integration, or
change the policy decision rules. The amount limits remain the existing
policy assumptions in the policy module.

## Proposed implementation commit plan (after approval)

1. **`feat(tools): add nullable source-faithful tool fields`** — amend the
   TSD-002 response/internal models and generated schemas; cover null handling
   and fail-closed writes.
2. **`feat(tools): add cleaned-table adapter`** — implement read-only
   DuckDB access, source mapping, local lineage metadata, and the synthetic
   table fixture.
3. **`test(tools): cover cleaned-table adapter conformance`** — register the
   adapter in the shared conformance, security, eligibility, and hub suites.
4. **`docs(tools): document cleaned-table adapter`** — update T-206,
   HANDOFF, and CHANGELOG; run full Ruff, format, pytest, Git-rule, and
   commit-size checks.

No implementation begins until the maintainer approves this specification.
