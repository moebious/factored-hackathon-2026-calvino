# T-104 headline baseline (independent cross-check) [measured]

Superseded as the published baseline by `reports/baseline/` (TSD-018, T-104):
every common headline cell matched, so the figures are unchanged. Preserved
unchanged for review.

Full live `data/` prefix; aggregates only. Reproduce with `python scripts/analysis/build_cache.py <tables>` then `python scripts/analysis/baseline.py`. Country is the customer's country (`customers.country` through `customer_id`). All numbers are `[measured]`. The CSVs hold every slice; this page shows the headline cells.

## Definitions (fixed before any number was read)

**Interactions** (`call_center_interactions`), for all interactions and for `reason_category = 'Transaccional'`, overall and by country:

- `fcr`: share with `was_resolved = true`; nulls excluded and counted.
- `escalation`: share with `was_escalated = true`.
- `follow_up`: share with `requires_followup = true`.
- `duration_seconds_*`, `wait_time_seconds_*`: mean, median and p90 (linear interpolation) over non-null values; nulls counted.

**Complaints** (`complaints`), for all complaints and for `category = 'Transactions'`, overall, by country, by `case_type` and by their product:

- `resolution_days_*`: mean, median, p90 over complaints with `status` Resolved or Closed and a non-null `resolution_days`; resolved complaints without a value are counted in `n_null_excluded`.
- `still_open_count`: complaints with `status` Open, In Process or Escalated (Rejected counts as neither open nor resolved); the denominator is all complaints in the slice.
- `sla_breached_share`: share with `sla_breached = true`.
- `compensation_granted_share_of_*`: `compensation_granted` holds an amount, not a flag, so granted means a non-null amount; shown over all complaints in the slice and over resolved/closed ones (amounts exist only on Resolved and Closed).

A cell is marked `small_n` when it rests on fewer than 30 cases. `n_cases` is the count the value is computed over; `n_null_excluded` counts records left out for a missing value.

## Interactions

| metric | all interactions / all | all interactions / Argentina | all interactions / Colombia | all interactions / México | Transaccional / all | Transaccional / Argentina | Transaccional / Colombia | Transaccional / México |
|---|---|---|---|---|---|---|---|---|
| fcr | 76.65%, n=686,296 | 76.59%, n=136,317 | 76.67%, n=206,790 | 76.66%, n=343,189 | 91.51%, n=240,056 | 91.57%, n=47,660 | 91.50%, n=72,511 | 91.49%, n=119,885 |
| escalation | 9.96%, n=686,296 | 9.84%, n=136,317 | 10.10%, n=206,790 | 9.93%, n=343,189 | 9.93%, n=240,056 | 9.76%, n=47,660 | 10.04%, n=72,511 | 9.93%, n=119,885 |
| follow_up | 34.83%, n=686,296 | 34.91%, n=136,317 | 34.80%, n=206,790 | 34.82%, n=343,189 | 22.14%, n=240,056 | 22.07%, n=47,660 | 22.10%, n=72,511 | 22.18%, n=119,885 |
| duration_seconds_mean | 321.5, n=590,062 | 321.7, n=117,103 | 321.4, n=177,907 | 321.4, n=295,052 | 220.8, n=206,465 | 220.2, n=41,004 | 221.0, n=62,408 | 220.9, n=103,053 |
| duration_seconds_median | 291.0, n=590,062 | 291.0, n=117,103 | 290.0, n=177,907 | 291.0, n=295,052 | 205.0, n=206,465 | 204.0, n=41,004 | 205.0, n=62,408 | 205.0, n=103,053 |
| duration_seconds_p90 | 538.0, n=590,062 | 539.0, n=117,103 | 538.0, n=177,907 | 538.0, n=295,052 | 333.0, n=206,465 | 331.0, n=41,004 | 333.0, n=62,408 | 334.0, n=103,053 |
| wait_time_seconds_mean | 119.9, n=480,678 | 120.0, n=95,386 | 119.7, n=145,009 | 120.0, n=240,283 | 119.7, n=168,074 | 120.1, n=33,483 | 119.4, n=50,692 | 119.6, n=83,899 |
| wait_time_seconds_median | 119.0, n=480,678 | 119.0, n=95,386 | 119.0, n=145,009 | 119.0, n=240,283 | 119.0, n=168,074 | 119.0, n=33,483 | 119.0, n=50,692 | 119.0, n=83,899 |
| wait_time_seconds_p90 | 196.0, n=480,678 | 196.0, n=95,386 | 196.0, n=145,009 | 196.0, n=240,283 | 196.0, n=168,074 | 197.0, n=33,483 | 196.0, n=50,692 | 196.0, n=83,899 |

## Complaints

Overall and by country here; `case_type` and country x case_type slices are in `complaints.csv`.

| metric | all complaints / all | all complaints / Argentina | all complaints / Colombia | all complaints / México | Transactions / all | Transactions / Argentina | Transactions / Colombia | Transactions / México |
|---|---|---|---|---|---|---|---|---|
| resolution_days_mean | 15.6, n=15,363 | 15.5, n=3,010 | 15.6, n=4,678 | 15.6, n=7,675 | 15.4, n=3,165 | 15.4, n=648 | 15.2, n=940 | 15.5, n=1,577 |
| resolution_days_median | 16.0, n=15,363 | 16.0, n=3,010 | 16.0, n=4,678 | 16.0, n=7,675 | 15.0, n=3,165 | 16.0, n=648 | 15.0, n=940 | 16.0, n=1,577 |
| resolution_days_p90 | 28.0, n=15,363 | 27.0, n=3,010 | 28.0, n=4,678 | 28.0, n=7,675 | 27.0, n=3,165 | 27.0, n=648 | 28.0, n=940 | 27.0, n=1,577 |
| still_open_count | 50,269, n=67,095 | 10,029, n=13,336 | 15,259, n=20,384 | 24,981, n=33,375 | 10,124, n=13,580 | 1,999, n=2,701 | 3,086, n=4,119 | 5,039, n=6,760 |
| sla_breached_share | 20.11%, n=67,095 | 20.41%, n=13,336 | 19.75%, n=20,384 | 20.22%, n=33,375 | 20.17%, n=13,580 | 20.25%, n=2,701 | 19.98%, n=4,119 | 20.25%, n=6,760 |
| compensation_granted_share_of_all | 6.92%, n=67,095 | 6.76%, n=13,336 | 7.13%, n=20,384 | 6.85%, n=33,375 | 7.33%, n=13,580 | 7.18%, n=2,701 | 7.53%, n=4,119 | 7.26%, n=6,760 |
| compensation_granted_share_of_resolved | 28.79%, n=16,121 | 28.43%, n=3,169 | 29.47%, n=4,931 | 28.51%, n=8,021 | 29.87%, n=3,331 | 28.53%, n=680 | 31.06%, n=998 | 29.70%, n=1,653 |

