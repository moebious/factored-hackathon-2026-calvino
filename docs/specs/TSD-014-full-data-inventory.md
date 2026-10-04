# TSD-014: Read-only inventory of the full dataset

| | |
|---|---|
| Status | implemented; full-data scan completed and aggregate findings reviewed |
| Branch | `feat/full-data-inventory` |
| Depends on | organizer's read-only dataset access; TSD-007 contracts for eight tables |
| Required by | the separate T-104 human baseline and any reassessment of the workflow choice |
| References | DATA.md; TSD-007; TSD-006 (superseded); decision 17 |

## Purpose and boundary

Recheck what the organizer's **full live** dataset actually contains before
implementing T-104. Inventory all 13 tables, not only the four used by the
baseline. This work measures structure and data quality; it does not choose
a new workflow, alter dataset records, build a clean layer, train a model,
or produce T-104's resolution and complaint metrics. Existing full-data
reports in DATA.md and `reports/data-quality/` are comparison targets, not
inputs to the new counts.

The maintainer has already confirmed a bounded `ListObjectsV2` and one-byte
`GetObject` against one expected file from their own terminal. That **does
not** establish coverage of every partition or permission for every table.
The full inventory runs only in a credentialed local process; this Droid
session does not inherit the maintainer's environment or the external `.env`.

The point of scanning all 13 tables is to **challenge the existing analysis**,
not to restate it. Counts, nulls, schema drift and safe category distributions
are recomputed by a new implementation from the source. An inventory alone
cannot establish the best workflow: candidate-specific outcome, grounding and
linkage tests follow in a separate analysis, and T-104 is a separate baseline.

## Source and access contract

The source is exactly the organizer's live S3 `data/` prefix, never the
dated backup. The 13 allowlisted table names are `customers`, `products`,
`branches`, `service_agents`, `marketing_campaigns`, `transactions`,
`call_center_interactions`, `call_transcripts`, `satisfaction_surveys`,
`digital_events`, `complaints`, `campaign_sends`, and
`daily_exchange_rates`. Small tables have a single CSV object; larger
tables use partitioned CSV objects under their table prefix. Discover
only those table paths, rejecting unexpected names, extensions and
objects outside the live prefix. Do not output bucket or object names.

Use Boto3 with the **user-owned `.env` outside all worktrees**, loaded
explicitly from `CALVINO_ENV_FILE` before creating the client. It provides
`AWS_ACCESS_KEY_ID`, the secret access key value, `AWS_DEFAULT_REGION`,
`CALVINO_DATA_BUCKET` and, for temporary credentials only,
`AWS_SESSION_TOKEN`. The runner does not create or modify the file.
Require an existing regular file with user-only permissions, reject
in-repo or symlink paths, and fail on incomplete or conflicting ambient
credentials. Never log values, paths, request URLs or raw exception text.
Test only with fake credentials. Boto3 and the dotenv loader are locked
project dependencies when implementation begins.

The runner calls only S3 list/read APIs. It never uploads, deletes, changes
ACLs, lists the bucket root, or reads another prefix. Fail on an unavailable
table or denied object rather than report a partial inventory as complete.

**Two gates before the full scan:**

1. A manifest-only command lists the 13 allowlisted table paths and reports
   per-table object counts and bytes, total bytes, partition coverage and a
   projected number of requests. It reads no table body. The maintainer
   reviews the transfer/storage estimate and confirms the full read; no
   dollar cost is claimed without an actual pricing basis.
2. The full-scan command requires an explicit byte ceiling at least as
   large as the reviewed manifest. It aborts if the manifest grows or
   changes before scanning; do not quietly cross that limit. A missing
   table, denied object or unexpected layout aborts before publication.

Direct streaming or column-oriented S3 querying is preferred if supported;
remote CSV scans may still transfer whole files. If remote scans fail,
propose the estimated storage and transfer for a local fallback **before**
staging any of the 13 tables. Local raw data, query spill and temporary
files must stay in this worktree's ignored `data/` with user-only
permissions, never in reports, fixtures, a synced folder or the deployed
demo storage. Do not automatically delete pre-existing local data.

## Inventory output

For **each table**, report:

- Source file and partition counts, total bytes of source objects, date or
  partition coverage when present, and full-row count. Do not report object
  keys or derive a date range from unrelated columns.
- Every column name, observed data type across partitions, number and rate
  of null or empty values, and schema drift (missing, extra or changed-type
  columns by partition). Type classification is a **coarse heuristic on CSV
  values**, not a schema declaration: numeric formats and empty partitions
  must not be called schema changes. A column name is metadata; never
  output a cell value while doing the schema inventory.
- Whether a TSD-007 contract exists. For its eight tables, require the
  columns used by the inventory and recompute row-local rule violations
  plus the small agent-to-branch link; known defects are counted, not
  cleaned away. State plainly that full PK/FK validation is **not**
  repeated by this streaming inventory and cite the existing TSD-007
  audit instead. For the other five, explicitly say **not
  contract-validated**. Unknown primary keys or relationships in those
  five are not inferred from similar-looking field names.

As a separate, allowlisted aggregate section, compute only safe
low-cardinality category distributions useful to the workflow decision,
such as transaction status/type, call reason category, complaint category
and status, country and currency. Record each distribution's population,
null count and denominator. Do not publish distinct values, examples,
top-k values or frequency tables for names, account or customer IDs,
transcript/complaint text, IP addresses, merchant fields or other
high-cardinality fields. Flag cells below 30 for maintainer review before
publication. No per-customer or per-case output, external model call or
unreviewed join that treats temporal proximity as causal evidence.

Write the detailed aggregate JSON into Git-ignored local staging and publish
a reviewed Markdown summary in `reports/data-quality/full-inventory.md`.
The first scan's CSV-value type flags are superseded by a targeted diagnostic;
do not publish them as schema drift. Record `[measured]` only for a complete full-data run,
the input file counts and byte totals, contract and code version, run date,
and comparison with DATA.md's 13 row counts and known defects. Include
a per-claim discrepancy table: old value, independently calculated value,
count/denominator or definition, and either the cause or "unresolved".
Do not smooth over mismatches or revise decision 17 without a separately
reviewed workflow analysis. Never silently overwrite older reports.
Draft output goes to an ignored staging path before maintainer review.
The report contains no bucket name, keys, credential path, records or
sensitive column values.

## Interface, tests and done criteria

One local CLI has `--check-access` (at most one byte), `--manifest` (object
metadata only), and `--run --max-source-bytes N` (the reviewed full scan).
After reviewing any type flags, `--review-types` may re-read only the
flagged tables under a separately approved byte cap; it emits a targeted
aggregate diagnostic, not a replacement full-data report.
The first two modes produce no raw copy. The full scan writes only
aggregate staging output unless the maintainer separately approves a
local raw fallback. A local fixture mode accepts synthetic CSV or Parquet
files for tests; CI never uses AWS credentials or the real dataset.

Tests cover all 13 table names, single-file and partitioned layouts,
UTF-8 BOM, missing files, schema drift, null/empty distinctions, read
denials, the live-prefix allowlist, contract coverage (eight vs five),
small cells, safe/unsafe categorical columns, failure without partial
`[measured]` output, manifest changes, byte ceilings, discrepancy reporting,
and redaction of errors and logs. Fake S3 calls verify that no write API
is invoked. Required repo checks are ruff
lint and format, pytest, and `tests/git/test_git_rules.sh`.

**Done when** the reviewed byte budget has been accepted, a full-data run has
checked every table and partition,
reconciled or explained all 13 counts and relevant defects, and produced
only reviewed aggregate artifacts. The earlier one-object probe alone
does not meet this criterion. Until the full run succeeds, the inventory
is implemented but **not measured or complete**.
