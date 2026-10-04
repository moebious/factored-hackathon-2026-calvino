# T-104 human baseline [measured]

Aggregate-only, category-level baseline over the organizer's full live `data/`
prefix: all interactions and `reason_category = 'Transaccional'`, and all
complaints and `category = 'Transactions'`. Country and segment are the
customer's, through `customers`.

These are **category-level proxies**, not case-level stuck-payment outcomes:
`complaints.origin_interaction_id` is null on every row and no call can be
linked to the payment that caused it. Never compare an automated
stuck-payment resolution rate with these figures as if the populations matched.

## Provenance

| | |
|---|---|
| Source | organizer live `data/` prefix, read-only S3, streamed with no local raw copy |
| Four-table manifest | digest `aad502d22e333512cb5051455674dca6ab1524b2fa10b30bb08d224fb68edeb7`; 2,196 objects; 205,401,834 bytes transferred |
| Call-table manifest | digest `f30407b5e0ad8029a48edab22361f35bbb2de7caf38d4fde80d32b20c40bceb5`; 1,097 objects; 139,734,950 bytes transferred |
| Source rows | customers 150,000; daily_exchange_rates 13,164; call_center_interactions 686,296; complaints 67,095 |
| Date ranges | FX 2023-06-17 to 2026-06-17; calls and complaints 2023-06-17 to 2026-06-18 |
| Known defects recounted | CI-REASON-REPEATS 686,296; CP-ORIGIN-NULL 67,095; CP-AMOUNT-NO-CURRENCY 1,040 |
| Reconciliation | 128 headline cells match `reports/baseline-independent/`; 108 grouped-channel cells match the first run |

## Reproduction

One command per step; credentials never appear in a command (see the README
quick start for the private `CALVINO_ENV_FILE`):

```bash
uv run python scripts/baseline/run.py --source live-s3 --check-access
uv run python scripts/baseline/run.py --source live-s3 --manifest-digest <reviewed-digest> --max-bytes <reviewed-ceiling>
uv run python scripts/baseline/channel_diagnostic.py --manifest
uv run python scripts/baseline/channel_diagnostic.py --run --manifest-digest <reviewed-call-digest> --max-bytes <reviewed-call-ceiling>
uv run python scripts/baseline/prepare_review.py
```

Every step is manifest-digest and byte-ceiling guarded and refuses a changed
source. Offline, the runner accepts synthetic fixtures
(`--source tests/fixtures/lakehouse`) and stages `candidate` output, never
`measured`.

## Definitions

Every CSV row is one metric in one named population and slice, with
`n_population`, `n_valid`, `n_null_excluded`, `n_invalid_excluded` (where
applicable), `n_unresolved_excluded` (complaint resolution statistics only) and
a clearly named `denominator`. Shares use non-null denominators; a zero
denominator leaves the value undefined, never zero. Percentiles use linear
interpolation. Resolution days cover Resolved or Closed complaints only.
Claimed amounts are reported per original currency (never pooled) and in USD
only over successfully converted claims, using the nearest-earlier
source-to-USD rate on `creation_date`. `small_n` flags fewer than 30 valid
cases: the value is kept but must not back a group-difference claim.

- `interactions.csv` (468 cells): overall, country, segment, channel and
  country x segment slices of fcr, escalation, follow-up, and mean, median and
  p90 handle and wait seconds.
- `complaints.csv` (960 cells): overall, country, case-type and country x
  case-type slices of still-open count, SLA breaches, resolution days,
  compensation shares and claimed amounts.
- `headline-reconciliation.csv`: cell-by-cell comparison with the independent
  cross-check.
- `channel-reconciliation.csv`: cell-by-cell comparison with the first run's
  grouped channels.

## Departures from the earlier cross-check

- **Web Chat:** the first guarded run grouped 22,856 calls (7,997
  Transaccional) as channel `(other)` because `Web Chat` was missing from its
  allowlist. The second guarded pass reports them as Web Chat; all six channel
  counts now sum exactly to the overall populations and every earlier grouped
  cell matches.
- **"Unknown" complaint categories:** the first staged README mislabelled the
  53,515 non-Transactions complaints as unknown. The full-data inventory found
  zero null categories, so they are non-target categories, not missing values;
  the complaint metrics were unaffected.

The cross-check's headline figures are unchanged by this re-measurement:
Transaccional fcr 91.51% (n=240,056), all calls 76.65% (n=686,296); median
resolution days 16.0 (all) and 15.0 (Transactions).
