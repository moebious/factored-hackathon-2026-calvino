# Full-data inventory [measured]

Read-only, full-row scan of the organizer's live `data/` prefix, independently
implemented as TSD-014 (precursor to T-104). The maintainer ran the scanner locally with a
private credential file outside the repository. Only aggregates are recorded
here; raw rows, bucket and object names, and credentials were not committed.
The [detailed aggregate profile](full-inventory.json) has per-column null
and coarse type counts, approved category distributions, per-table source
bytes and partition coverage. It contains no individual records. The scan
ran on 2026-10-03 under TSD-014 against the TSD-007 contracts; the code
was still uncommitted at measurement time, so its exact commit remains a
provenance gap until this branch is committed.

**Coverage:** 13 tables, 7,671 source objects, 5,349,322,481 source bytes
(5.35 GB), 23,495,188 rows. The reviewed manifest digest is
`a5ec571c6eeb36c7cf5390f49637ac2ef25a6e38f6b2da775354f6ef1f72f4a2`.
The partitioned tables generally cover 17 June 2023 to 17 June 2026;
`campaign_sends` starts 1 July 2023. These are partition dates, not
per-record event-date minima or maxima.

| Table | Rows independently counted | Objects | Earlier DATA.md rows | Difference |
|---|---:|---:|---:|---:|
| customers | 150,000 | 1 | 150,000 | 0 |
| products | 400,000 | 1 | 400,000 | 0 |
| branches | 350 | 1 | 350 | 0 |
| service_agents | 1,200 | 1 | 1,200 | 0 |
| marketing_campaigns | 200 | 1 | 200 | 0 |
| transactions | 4,425,008 | 1,097 | 4,425,008 | 0 |
| call_center_interactions | 686,296 | 1,097 | 686,296 | 0 |
| call_transcripts | 171,321 | 1,097 | 171,321 | 0 |
| satisfaction_surveys | 212,759 | 1,097 | 212,759 | 0 |
| digital_events | 15,620,994 | 1,097 | 15,620,994 | 0 |
| complaints | 67,095 | 1,097 | 67,095 | 0 |
| campaign_sends | 1,746,801 | 1,083 | 1,746,801 | 0 |
| daily_exchange_rates | 13,164 | 1 | 13,164 | 0 |
| **Total** | **23,495,188** | **7,671** | **23,495,188** | **0** |

**Recounted defects:** null transaction `response_code` 221,033; unaccented
`Mexico` transaction-country label 40,515; complaints with an amount but
no currency 1,040; complaints without `origin_interaction_id` 67,095;
interactions where `contact_reason` repeats `reason_category` 686,296;
agent-to-branch orphans 831. All match the earlier data-quality report.
Transaction status and currency, customer country, product currency and
exchange-rate positivity have zero row-local violations under the implemented
checks. The scanner found **no missing or extra column headers** among the
partitioned files.

The initial scan's `files_with_type_changes` numbers were from a coarse
CSV-value heuristic, **not a schema change**. A separately approved,
1,152,300,576-byte targeted reread of transactions (4,425,008 rows),
complaints (67,095) and campaign sends (1,746,801) with a corrected
numeric-family heuristic found zero incompatible-type-family flags and zero
header drift in those three tables. It did not repeat the other ten tables
under the new heuristic. The original JSON remains in the Git-ignored
staging folder as an audit artifact and is **not** a publishable final type
assessment. The published detailed profile removes those superseded flags
and records the separately reviewed targeted result; it does not claim the
other ten tables were re-read after that correction.

**Limits:** TSD-007 contracts cover eight tables; five were inventoried but
not contract-validated. The new streaming scan recounted row-local rules
and the agent-to-branch link, but did not rerun every primary/foreign-key
check; the prior contract audit covers those checks. Its zero-discrepancy
result refers only to the counts and known rules listed above, not to every
possible relationship. It does not attribute calls to transactions or
establish that stuck payments is the best workflow. T-104 still needs its
own full-data human baseline with denominators and slices.
