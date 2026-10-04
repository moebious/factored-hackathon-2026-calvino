# TSD-018: Full-data human baseline

| | |
|---|---|
| Status | done: published in `reports/baseline/`; the independent cross-check is preserved at `reports/baseline-independent/` |
| Branch | `eval/baseline` |
| Task | [T-104](../tasks/T-104-human-baseline.md) |
| Depends on | T-101 (workflow choice), TSD-007 (data contracts), TSD-014 (merged full-data inventory) |
| Requirements | BRD 3; DESIGN 7 and 8; DATA.md handling rules |

## Purpose and boundary

Establish a reproducible human baseline for all calls and `Transaccional` calls, and for
all complaints and `Transactions`-category complaints, on the organizer's **full live**
dataset. These are category-level proxies, not a measured baseline for individual stuck
payments: calls cannot be linked to the payment that caused them, and
`complaints.origin_interaction_id` is null. Do not compare an automated stuck-payment
resolution rate with the category-level first-contact rate as if the populations matched.

The existing independent cross-check (preserved at `reports/baseline-independent/`)
is the comparison target,
not the input to a new calculation. The analyst's two-week pilot is never a source for
published figures. This task does not rebuild the analyst's clean-all-tables pipeline,
choose a workflow, generate classifier labels, or measure Calvino's outcomes.

## Prerequisite: full-dataset inventory (complete)

TSD-014's read-only inventory was merged as #50 and recounts all 13 tables
and the known defects. It establishes source counts and schema coverage,
**not** T-104's resolution metrics or a case-level link between a call and
a payment. Use its aggregate report as a cross-check; this baseline must
independently compute its own populations and denominators from the full
live tables. There is no T-107 task in the merged backlog: the inventory
was folded into T-104's precursor.

## Inputs and access

| Table | Columns needed | Use |
|---|---|---|
| `customers` | `customer_id`, `country`, `segment` | Country and segment of the customer |
| `call_center_interactions` | `interaction_id`, `customer_id`, `interaction_date`, `reason_category`, `contact_reason`, `channel`, `was_resolved`, `was_escalated`, `requires_followup`, `duration_seconds`, `wait_time_seconds` | Call population, outcomes and known-defect count |
| `complaints` | `complaint_id`, `customer_id`, `category`, `case_type`, `status`, `sla_breached`, `resolution_days`, `compensation_granted`, `claimed_amount`, `currency`, `creation_date`, `origin_interaction_id` | Investigation population, outcomes and known-defect count |
| `daily_exchange_rates` | `date`, `source_currency`, `target_currency`, `exchange_rate` | Convert non-null claims with known currency to USD |

An optional CSAT metric requires a separately documented, tested linkage to
`satisfaction_surveys`; omit it rather than infer a link from customer and time.
Transaction-level workflow volume belongs to a separate analysis, not this baseline.

The read-only runner accepts a local directory of contracted CSV or Parquet
files, or the organizer's S3 **live `data/` prefix**. Reuse the merged
`calvino.data.inventory_access` credential loader, Boto3 client, allowlisted
table discovery, sanitized errors and source-version checks. Both Boto3 and
python-dotenv are already locked in the project. Do not add a second
credential path or copy keys into a DuckDB SQL string. The client uses
Boto3's default credential chain after the external file is loaded:

```python
import boto3

s3 = boto3.client("s3")
```

The maintainer-selected local credential path is a **user-owned `.env` file
outside every repository worktree**, outside cloud-synced folders, with
local-user-only file permissions. It holds `AWS_ACCESS_KEY_ID`, the secret
access key value, `AWS_DEFAULT_REGION` and `CALVINO_DATA_BUCKET`,
plus `AWS_SESSION_TOKEN` only if the organizers issued temporary credentials.
The file path (not its contents) is supplied through `CALVINO_ENV_FILE`.
`calvino.data.inventory_access.load_credentials` loads that file; Boto3 alone
does not load `.env`. Refuse missing files, files inside the repo, permissive
file permissions and ambiguous mixtures of process credentials and `.env`
credentials, without echoing values or paths. The runner never creates,
edits or commits the file, and its tests use only fake credentials.
File-based secrets are still plaintext at rest: Git-ignored is not encryption.
The maintainer chooses its location and protects it from backups and syncing.
The bucket name and credentials must never be passed as command-line arguments,
committed, printed or included in error messages. The S3 connector is not
required: a failed connector login does not establish whether these read-only
credentials work with Boto3. An already-running Droid process does not
automatically see environment variables set later in another terminal; a live
run must execute in the environment configured for that run. No `.env` file
or secret values are sent to this chat.

The one-byte permission probe passed during TSD-014. A new run still checks
the source manifest, **only the four required tables**, and an explicit byte
ceiling before any full-body read; the earlier probe does not grant unlimited
future reads. Report sanitized errors, never a bucket or object name.
Do **not** upload a test object, delete or modify objects, or broaden IAM
permissions automatically. If manifest discovery or access fails, stop.

The runner never reads the dated backup, writes to S3, embeds bucket or object names
in source or reports, or prints credentials, raw rows or object keys.

For the full run, stream selected columns from the four tables through the
shared read-only Boto3 source contract. Use DuckDB for aggregation over a
streamed or locally staged, narrow temporary relation only when it can be
done without embedding credentials in SQL. Otherwise compute bounded
aggregates from CSV streams. Local staging of raw tables requires a separate
byte/storage review before use; it is not the default. CSV still transfers
the relevant full objects even if only some columns are projected. Record
bytes read and wall time. Never call the existing all-table downloader by
default or load every partition into one pandas DataFrame merely to cache it.

## Data treatment and project controls

This is a **read-only offline analysis**, not the customer's live service path.
Apply these controls regardless of whether the source is S3 or an authorized local
copy:

1. **Minimize:** read only the four tables and named columns above. Identifiers
   (`customer_id`, `interaction_id`, `complaint_id`) are for joins and duplicate
   checks inside the analysis process; never publish or send rows, identifiers,
   texts or object paths to an LLM, external analytics service, CI job or log.
   `customers.segment` is a reporting dimension, not an input to the policy
   decision. No transcripts, complaint descriptions, IP addresses or payment
   details are required.
2. **Separate and contain:** direct S3 reads produce no durable raw copy. If
   fallback staging is needed, use only this worktree's root `data/` directory
   (ignored by `.gitignore`) with local-user-only permissions; never use
   `reports/`, `tests/fixtures/`, `/data` for the deployed demo, a shared
   worktree or a cloud-synced folder for raw tables. Treat DuckDB spill files,
   temporary directories and exception traces as potentially containing raw
   data: put them under an ignored, access-restricted local directory and do
   not publish them.
3. **Validate before aggregation:** require all four tables, the columns named
   above, and the TSD-007 error-level rules that apply to them. Use the raw
   contract checks even when no cleaned layer exists. Count known defects
   rather than silently dropping rows. Apply `DATA.md` currency and linkage
   rules; a null transaction `response_code` is never a failure signal.
   Report row counts, join coverage, nulls, FX coverage and any unrecognized
   values so unsupported data cannot quietly change a denominator.
4. **Publish aggregates only:** outputs contain metric names, population labels,
   grouping labels, counts, denominators and summary statistics. No
   per-customer or per-case extracts. Do not publish tiny example rows or
   diagnostic samples. Flag `small_n` cells; the maintainer reviews any
   small-cell disclosure risk before publishing, even though the organizer's
   dataset is synthetic.
5. **Provenance and cleanup:** record source as the organizer's live `data/`
   prefix, dataset version or run date when known, input file counts and
   non-sensitive hashes, contract version, code commit and aggregate row
   counts, without recording bucket names or object keys in committed output.
   Local staged raw data and query spill remain ignored and are not retained
   as deliverables. The runner must never automatically delete pre-existing
   user files; offer an explicit cleanup step after the run and confirm its
   scope before removing staged files.

These controls align this task with the repository's data and secret rules and
its stated demo data boundary. They do **not** certify compliance with an
organizer's data-use terms, banking privacy law or a production security review;
the maintainer must check those obligations separately.

## Metrics and definitions

**Population:** one row per primary key (the contract audit must report duplicate and
missing keys); do not silently drop records. Join each call or complaint to `customers`
by `customer_id`, report unmatched customer counts, and fail rather than publish a
country/segment slice with an unaccounted join. Use the customer's country, not an IP or
transaction-country label. State the source row counts, date range and null counts.

**Call slices:** all interactions and `reason_category = 'Transaccional'`, each overall,
by customer country, by customer segment, by call channel, and by country x segment.
For each slice:

- First-contact resolution = `was_resolved = true` / non-null `was_resolved`.
- Escalation = `was_escalated = true` / non-null `was_escalated`.
- Follow-up = `requires_followup = true` / non-null `requires_followup`.
- Handle and wait time = mean, median and p90 seconds over valid non-null, non-negative
  values, with invalid and null counts separate. State the percentile interpolation
  method and keep it identical to the existing cross-check (linear).

**Complaint slices:** all complaints and `category = 'Transactions'`, each overall, by
customer country, by case type, and by country x case type:

- Still open = count with `status` in Open, In Process or Escalated, divided by all
  complaints in the slice; Rejected is neither open nor resolved.
- Resolution days = mean, median and p90 for Resolved or Closed complaints with a
  valid non-null `resolution_days`; report unresolved and excluded-null counts.
- SLA breached = `sla_breached = true` / non-null `sla_breached`.
- Compensation granted = non-null amount in `compensation_granted`, as a share of
  (a) all complaints and (b) Resolved or Closed complaints. It is an amount, not a flag.
- Claimed amount = count with a non-null amount, count without currency or conversion
  rate, mean and median by original currency, and a separate USD mean and median only
  over successfully converted claims. Use `daily_exchange_rates` for source -> USD
  on `creation_date` or the closest earlier date; multiply by that rate. USD -> USD
  uses 1. Never pool native amounts from different currencies.

Every reported statistic has `n_population`, `n_valid`, `n_null_excluded` (and
`n_invalid_excluded` when applicable), plus a clearly named denominator for rates.
Flag a cell with fewer than 30 valid cases as `small_n`; keep its value and count but
do not use it to claim a group difference. A zero denominator yields `not defined`,
not zero. Report unknown category/status/currency values rather than guessing.

## Output and interface

An implementation command, to be finalized with the access adapter, runs the entire
baseline in one invocation, for example:

```text
uv run python scripts/baseline/run.py --source <local-dir>
```

For S3, `--source live-s3` loads `CALVINO_ENV_FILE` as above, never a URL
containing credentials. A `--check-access` mode performs only the bounded
read-only probe and produces no local data copy. Tests use `--source` on
synthetic fixtures and do not need network access, a GPU, or the real dataset.

The command prepares aggregate-only `interactions.csv`, `complaints.csv` and a
README with definitions, denominators, provenance (`[measured]` for full-data
runs), source row counts, missingness, small-sample flags and any departures
from the earlier independent cross-check. Write them to an ignored staging
directory under the worktree's `data/` first. Only after validation and an
explicit comparison with the existing report may they replace the files in
`reports/baseline/`; preserve the independent report for review. Runtime output
is a brief count/status summary, not records, object keys, bucket names or
credentials. No raw table or per-customer output is committed.

## Validation and acceptance

When a full-data run groups non-null call channels as `(other)`, a separately
reviewed one-table diagnostic may recompute the channel slices only. It must
reconcile all earlier grouped channel cells, use its own unchanged manifest
digest and byte ceiling, and stage aggregates separately without overwriting
the four-table output. A manifest listing alone does not authorize its read.

- Synthetic fixtures cover the populations and all slices, null denominators, zero
  denominators, missing customers, duplicate keys, missing/invalid durations,
  unresolved complaints, compensation as an amount, mixed currencies and nearest
  earlier FX rate (including missing rates and ties). CSV and Parquet yield the same
  aggregates.
- A fake or stubbed S3 client proves that the access probe lists at most one
  object under `data/customers.csv`, reads at most one byte of it, and closes
  the response; the full scan never includes the backup, and error handling
  does not print keys or configuration. CI never needs AWS credentials.
- Credential-loading tests use a synthetic external `.env` fixture, reject
  missing or in-repo paths, permissive file modes and conflicting ambient
  credentials, and show that the report and errors contain neither file path
  nor secret values. No test uses a real credential.
- Synthetic tests also prove only allowlisted columns are projected, staged
  paths are worktree-local and ignored, no raw values enter logs or reports,
  no existing local file is silently deleted, and known defects are counted.
- A full-data run checks source and population counts against DATA.md and the
  TSD-007 audit. Compare the common overall/country cells to the independent
  `reports/baseline/` cross-check, explain differences, and add channel, segment,
  claimed-amount and conversion coverage without overwriting unexplained values.
- The command exits nonzero on missing required tables, failed contract checks,
  unaccounted joins or unsupported schema; a denied S3 permission is reported
  without suggesting uploads or expanded privileges.
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`, and
  `bash tests/git/test_git_rules.sh` pass. The README contains the actual
  one-command reproduction instructions for the chosen source and no credentials.

**Done when** the complete full-data baseline can be reproduced from one command,
its aggregate counts and denominators are reported, the earlier baseline is
reconciled, and the maintainer approves its use as a category-level comparator.
If live S3 access remains unavailable, the implementation and fixtures may be
reviewed but T-104 stays incomplete; do not label synthetic output `[measured]`.
