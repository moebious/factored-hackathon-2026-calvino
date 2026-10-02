# Dataset summary

*What the supplied data contains and how Calvino uses it. Credentials, bucket names and records are never written into the repository; access is configured through environment variables (see HANDOFF.md).*

## Overview

Synthetic **LATAM Bank** dataset, version 1.0.0, supplied by the organizers: 13 tables, 23,495,188 rows in the `data/` prefix `[measured]` (the data dictionary says about 19 million), Mexico, Colombia and Argentina, June 2023 to June 2026. Currencies MXN, COP, ARS and USD. All text is Spanish (Mexican, Colombian, Argentine variants). **No Portuguese.**

Deliberate quality problems, as described by the organizers: about 2% duplicate records, about 5% nulls in nullable fields, late-arriving partitions, schema evolution, and a small share of orphan foreign keys. On the `data/` prefix we measured no duplicate primary keys, orphans only in one link (see Findings), and nulls of about 5% `[measured]`; the described duplicates may sit in the dated backup, which we have not read.

Large fact tables are partitioned by `process_date`.

## Tables

| Table | Rows | Kind | Used by Calvino for |
|---|---|---|---|
| `customers` | 150,000 | dimension | segment, country, accent; fairness slices; demo personas |
| `products` | 400,000 | dimension | account and card status, limits, days past due; grounding |
| `branches` | 350 | dimension | not used |
| `service_agents` | 1,200 | dimension | not used (possibly agent specialty for routing context) |
| `marketing_campaigns` | 200 | dimension | not used |
| `transactions` | 4,425,008 | fact | **the workflow (decision 17):** status, type, amount, merchant, channel, fraud flag; grounding answers and the simulated actions |
| `call_center_interactions` | 686,296 | fact | **contact reasons (six coarse categories), resolution, escalation, handle time, sentiment**: the baseline and proxy labels |
| `call_transcripts` | 171,321 | fact | **templated:** 42 distinct customer texts, the same under every category; not used as model input (decision 16), reported as a data-quality finding |
| `satisfaction_surveys` | 212,759 | fact | CSAT for the baseline, if used |
| `digital_events` | 15,620,994 | fact | not used |
| `complaints` | 67,095 | fact | the investigation baseline: Transactions category, resolution days, SLA, compensation |
| `campaign_sends` | 1,746,801 | fact | not used |
| `daily_exchange_rates` | 13,164 | reference | currency questions only |

## Key columns

- `call_center_interactions`: `contact_reason` and `reason_category` (the same six values: Comercial, Producto, Queja, Retención, Transaccional, Técnico), `channel`, `was_resolved`, `was_escalated`, `requires_followup`, `duration_seconds`, `wait_time_seconds`, `detected_sentiment`, `customer_detected_accent`, `has_transcript`.
- `call_transcripts`: `interaction_id`, `customer_text`, `agent_text`, `detected_language` (only `es`), `detected_accent`, `detected_intents` (one value), `main_topics` (the six categories).
- `transactions`: `transaction_type` (Deposit, Withdrawal, Transfer, Payment, Purchase, Adjustment), `transaction_status` (Approved, Declined, Pending, Reversed), `is_fraud`, `fraud_score`, `merchant_name`, `channel`.
- `complaints`: `case_type`, `category`, `subcategory`, `status`, `priority`, `sla_breached`, `resolution_days`, `compensation_granted`, `is_repeat_complainer`.
- `customers`: `segment` (Premium, Plus, Basic, Student), `country`, `detected_accent`, `credit_score`.

## Storage layout

The bucket holds a `data/` folder (the current data) and a dated backup folder. Use `data/` only. The maintainer also has a cleaned layer (parquet) from earlier work, which can serve as the clean layer once its schema is described by the contracts (T-102).

## Findings `[measured]`

Measured on the full `data/` prefix. Deduplication on primary keys removes nothing.

| Finding | Measurement | Consequence |
|---|---|---|
| One reason level | `contact_reason` repeats the six values of `reason_category` | no fine-grained contact reasons |
| Templated transcripts | 42 distinct `customer_text` values (digits masked) in 171,321 transcripts, built from two fixed openings (both balance enquiries) and generic closers, identical across all six categories | not used as model input; classifier text is team-generated (decision 16) |
| Templated complaint text | 5 distinct `description` values in 67,095 complaints, one per category | adds no information |
| Independent fields | all 36 `transaction_type` × `channel` pairs occur, including implausible ones | the generator fills fields independently |
| Links between tables at chance | calls after a problem transaction within 7 days: 1.48% observed vs 1.48% with timestamps shuffled within customer (100 permutations); web errors within 15 minutes of a problem transaction: 16 observed vs about 14 expected | the data cannot attribute a call to the transaction behind it; the workflow was chosen on single-table volumes (decision 17) |
| Problem transactions | 354,327 of 4,425,008 (8.0%) are Declined, Pending or Reversed, the same rate in each country | the workflow's grounding volume |
| Contact demand | Transaccional is 240,056 of 686,296 calls (35%) | the workflow's demand |
| Uniform nulls | `response_code` is null on about 5% of transactions in every status, Approved included | a deliberate defect, not a signal |
| Web errors | the `Error` rate is 6.0% on the transactions, transfer and payments pages and 4.5% on help, home, products and accounts | payments are not special |
| Broken foreign key | `service_agents.assigned_branch_id`: 2 of 833 non-null values exist in `branches` | reported, not cleaned: dropping would delete 831 of 1,200 agents |
| Complaints without origin | `complaints.origin_interaction_id` is null on all 67,095 rows | a complaint cannot be linked to the call that caused it |
| Anonymous events | `digital_events.customer_id` is null on 3,745,446 rows (24%) | a quarter of the telemetry cannot be attributed |
| Mixed currencies | `claimed_amount` is in MXN, COP, ARS and USD; only 1,308 of 3,335 Transactions claims carry an amount | convert with `daily_exchange_rates` before summing or averaging |
| Foreign countries as labels | `transaction_country` has Brazil, USA, Spain and a "Mexico" variant next to "México", about 0.9% each, spread evenly over customers of every country | no foreign markets; normalise the spelling |
| Human baseline (calls) | Transaccional calls: first-contact resolution 91.5%, escalation 9.9%, follow-up 22.1%, median handle time 205 s (all calls: 76.7%, 10.0%, 34.8%, 291 s); the same in every country | the target is to **match** the human 91.5% with zero unsafe outcomes at lower time and cost, not to beat it; the room to improve is in investigations |
| Human baseline (complaints) | Transactions-category complaints: 74.5% still open, SLA breached on 20.2%, median 15 days to resolve among resolved ones | investigations are where the improvement story sits; time savings there can only be projected, never measured |
| No card details | no card table and no EMV, 3DS, CVV, PAN or BIN fields; cards exist only as a product type | rules and checks use the fields that exist |

A teammate's pilot lakehouse covers a two-week window (17–30 June 2023): 878,336 rows with every dimension table and the fact tables for that window. Its rates match the full data (problem transactions 7.87% vs 8.0%), so it serves as a development subset; every published figure comes from the full data.

## Handling rules

- Download only the tables a task needs, into the git-ignored `data/` folder.
- Outputs committed to the repository are aggregates only, never records.
- Test fixtures are small, synthetic and labelled synthetic.
- Payment status comes from `transaction_status` only; a null `response_code` never means a failure.
- Country labels map to ISO 3166 codes, and `Mexico` is merged into `México` (MX). For Mexican customers this turns about 18,400 rows domestic; no rule depends on it, because the foreign share carries no signal.
- Amounts are converted to USD with `daily_exchange_rates` (rate on the date, or the nearest earlier one) before any sum or average across currencies.
- A complaint is linked to activity by customer and time window, never by `origin_interaction_id`, and any such link is checked against a shuffled baseline before it is reported.
- Synthetic data uses MXN, COP, ARS or USD and the countries MX, CO, AR (US only as a foreign label); never BRL or Brazilian customers.

The baseline rows above come from the analysis session's independent run (`reports/baseline/`); they are published only after comparison with the analyst's own figures (HANDOFF next action 5).
