# Dataset summary

*What the supplied data contains and how Calvino uses it. Credentials, bucket names and records are never written into the repository; access is configured through environment variables (see HANDOFF.md).*

## Overview

Synthetic **LATAM Bank** dataset, version 1.0.0, supplied by the organizers: 13 tables, about 19 million rows, Mexico, Colombia and Argentina, June 2023 to June 2026. Currencies MXN, COP, ARS and USD. All text is Spanish (Mexican, Colombian, Argentine variants). **No Portuguese.**

Deliberate quality problems: about 2% duplicate records, about 5% nulls in nullable fields, late-arriving partitions, schema evolution, and a small share of orphan foreign keys. The duplicates are data-quality duplicates, not customer-facing duplicate charges.

Large fact tables are partitioned by `process_date`.

## Tables

| Table | Rows | Kind | Used by Calvino for |
|---|---|---|---|
| `customers` | 150 K | dimension | segment, country, accent; fairness slices; demo personas |
| `products` | 400 K | dimension | account and card status, limits, days past due; grounding |
| `branches` | 350 | dimension | not used |
| `service_agents` | 1.2 K | dimension | not used (possibly agent specialty for routing context) |
| `marketing_campaigns` | 200 | dimension | not used |
| `transactions` | 5 M | fact | grounding answers and actions: status, type, merchant, fraud flag |
| `call_center_interactions` | 800 K | fact | **contact reasons, resolution, escalation, handle time, sentiment**: the baseline and labels |
| `call_transcripts` | 200 K | fact | **customer text** for classifiers; beware derived fields (`detected_intents`, `detected_keywords`, `main_topics`) as leakage |
| `satisfaction_surveys` | 250 K | fact | CSAT for the baseline, if used |
| `digital_events` | 10 M | fact | not used |
| `complaints` | 80 K | fact | complaint categories, SLA, resolution, compensation; demand evidence and grounding for complaint follow-up |
| `campaign_sends` | 2 M | fact | not used |
| `daily_exchange_rates` | 3 K | reference | currency questions only |

## Key columns

- `call_center_interactions`: `contact_reason`, `reason_category`, `channel`, `was_resolved`, `was_escalated`, `requires_followup`, `duration_seconds`, `wait_time_seconds`, `detected_sentiment`, `customer_detected_accent`, `has_transcript`.
- `call_transcripts`: `interaction_id`, `customer_text`, `agent_text`, `detected_language`, `detected_accent`, `detected_intents` (leakage risk).
- `transactions`: `transaction_type` (Deposit, Withdrawal, Transfer, Payment, Purchase, Adjustment), `transaction_status` (Approved, Declined, Pending, Reversed), `is_fraud`, `fraud_score`, `merchant_name`, `channel`.
- `complaints`: `case_type`, `category`, `subcategory`, `status`, `priority`, `sla_breached`, `resolution_days`, `compensation_granted`, `is_repeat_complainer`.
- `customers`: `segment` (Premium, Plus, Basic, Student), `country`, `detected_accent`, `credit_score`.

## Storage layout

The bucket holds a `data/` folder (the current data) and a dated backup folder. Use `data/` only. The maintainer also has a cleaned layer (parquet) from earlier work, which can serve as the clean layer once its schema is described by the contracts (T-102).

## Handling rules

- Download only the tables a task needs, into the git-ignored `data/` folder.
- Outputs committed to the repository are aggregates only, never records.
- Test fixtures are small, synthetic and labelled synthetic.
