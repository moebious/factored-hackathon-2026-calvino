# TSD-007: Data contracts, validator and lineage

| | |
|---|---|
| Status | draft |
| Branch | `feat/data-contracts` |
| Task | [T-102](../tasks/T-102-data-contracts.md) |
| Depends on | TSD-000 |
| Required by | T-103, T-104, T-105, T-106, T-206 |
| References | DATA.md (findings and handling rules); `reports/data-quality/`; decisions 16 and 17 |

## Purpose

Make data preparation checkable, as the brief asks ("repeatable data preparation with contracts, quality checks, lineage"): every table Calvino uses has a contract, a validator measures each table against it, and known defects are reported, never cleaned away.

## Scope

The tables Calvino uses (DATA.md): `customers`, `products`, `transactions`, `complaints`, `call_center_interactions`, `daily_exchange_rates`, and `service_agents` with `branches` for their foreign key. Tables Calvino does not use are out of scope.

## Interfaces

**`calvino.data.contracts`**
- One Pydantic model per table, covering the columns Calvino reads; other columns are ignored, so the contracts work on the raw files and on the cleaned layer alike.
- `TABLES`: a registry of `TableContract` (name, model, primary key, foreign keys, date column) and `RULES`: SQL checks, each with an id, a severity and the DATA.md rule it encodes.
- Severity `error` fails the table; severity `known_defect` is counted and reported but never fails (DATA.md: "reported, not cleaned").

**`calvino.data.validator`**
- `validate_records(table, rows)`: row-level validation with the Pydantic model, for fixtures and samples.
- `audit(directory)`: table-level checks run as DuckDB aggregate queries over Parquet or CSV files, so the full data (4.4M transactions) never passes through Python row by row. Per table: row count, empty and duplicate primary keys, nulls in required columns, orphan foreign keys, and every rule's violation count.
- Returns an `AuditReport` that serialises to JSON; `passed` is false only when an `error` check fails.

**Scripts**
- `scripts/validate_data_contracts.py --dir <path> [--output report.json]`: runs the audit; exit code 1 on errors.
- `scripts/export_data_schemas.py`: writes the JSON Schemas to `contracts/data/`.

**Lineage**: `contracts/data/lineage.json` records each step from the organizer's source files to the validated layer: input, script, what it changes, and what it deliberately does not change.

## Rules (from DATA.md)

| Rule id | Table | Severity | Check |
|---|---|---|---|
| `TX-STATUS` | transactions | error | status in Approved, Declined, Pending, Reversed |
| `TX-CURRENCY` | transactions | error | currency in MXN, COP, ARS, USD |
| `TX-RESPONSE-CODE-NULL` | transactions | known_defect | null `response_code` (about 5% in every status; never a failure signal) |
| `TX-COUNTRY-MEXICO` | transactions | known_defect | `transaction_country = 'Mexico'` (merged into México, ISO 3166 MX) |
| `CU-COUNTRY` | customers | error | country in México, Colombia, Argentina (no Brazilian customers) |
| `PR-CURRENCY` | products | error | currency in MXN, COP, ARS, USD, when present |
| `CP-AMOUNT-NO-CURRENCY` | complaints | known_defect | `claimed_amount` without a currency |
| `CP-ORIGIN-NULL` | complaints | known_defect | null `origin_interaction_id` (100% in the full data; link by customer and time) |
| `CI-REASON-REPEATS` | call_center_interactions | known_defect | `contact_reason` equal to `reason_category` (one reason level) |
| `FX-RATE-POSITIVE` | daily_exchange_rates | error | `exchange_rate > 0` |
| `SA-BRANCH-ORPHAN` | service_agents | known_defect | `assigned_branch_id` missing from `branches` (2 of 833 exist; dropping would delete most agents) |

Foreign keys are checked as orphan counts: severity `error`, except the agent-to-branch link above.

## Tests and acceptance

- A small synthetic fixture (`tests/fixtures/lakehouse/`, CSV, labelled synthetic) with deliberate defects: each rule fires the expected number of times, and known defects do not fail the audit.
- The same fixture written as Parquet gives the same report.
- Row-level validation accepts valid rows and rejects malformed ones with the field named.
- JSON Schemas export and match the models.
- No network, credentials or real data.

**Done when** the audit runs on the fixture in CI and the report shows violation counts per rule.
