# TSD-021: Update-correctness fixture (T-105)

| | |
|---|---|
| Status | implemented and merged in #81 |
| Branch | `feat/freshness-fixture` (`data/` is not an allowed branch type in the push hook) |
| Task | [T-105](../tasks/T-105-freshness-fixture.md) |
| Depends on | T-102 / TSD-007; T-103 / TSD-015 and T-106 / TSD-019 interfaces only |
| Consumed by | T-407 and T-408; this spec defines no task-specific promotion API |
| Blocked by | — |
| Design | DESIGN.md 8.2; decision 34 |

## Workflow context

The customer workflow remains explain, clarify, act under the Gate, investigate,
and follow up. T-105 does not change that runtime. It protects the separate,
offline learning path: a late or corrected source record must not leave derived
labels or candidate evidence silently describing an older dataset version.

T-407 will use corrected-input handling as one input to its governed offline
learning turn. T-408 is a downstream consumer of versioned evidence, but its
policy replay and scorecard are outside this task. T-105 supplies a fixture and
freshness boundary only; it does not define either consumer's orchestration,
candidate format, scorecard, or promotion decision.

## Purpose and boundary

Demonstrate, using small synthetic files, that a correction or late record:

1. is traced from the source revision through affected process-date partitions,
   derived labels, and candidate-promotion evidence;
2. rebuilds only affected, non-frozen outputs;
3. makes stale artifacts impossible to reuse silently; and
4. cannot leak corrected held-out records into training or rewrite the frozen
   T-303 suite.

This is an offline update-correctness fixture. It does not implement continuous
production ingestion, read the live dataset, train or promote a model, or claim
that production drift has been detected.

## Mapping to existing artifacts

The fixture uses small explicit stand-ins for the real downstream artifact
families; it does not generate or mutate production artifacts:

- **TSD-019 seed facts:** a synthetic transaction amount and currency derive a
  policy-versioned `amount_band` (`under_gate` / `over_gate`) and fixture
  `expected_outcome` (`ExpectedOutcome.ACT_ALLOW` /
  `ExpectedOutcome.ACT_ASK` from `calvino.evaluation.oracle`).
  Use the actual `gate.allow_amount_limit` from the referenced
  `policy/v2.yaml` (policy assumptions); record `policy_version: v2` and a
  lineage source hash of the canonical JSON serialization of only the
  `gate.allow_amount_limit` mapping (sorted keys, compact separators).
  Comments and unrelated policy fields do not affect this digest.
  `under_gate` maps to `ACT_ALLOW`; `over_gate` maps to `ACT_ASK`. This fixture
  holds every other oracle fact fixed to an unambiguous, in-scope, owned,
  eligible retry on a Declined transaction with no fraud, so amount band is
  the only changing outcome input. This mapping
  proves dependency invalidation, not a full policy verdict, model result, or
  new policy. It models the amount-band → expected-outcome chain.
  TSD-019 seed facts and messages remain immutable once committed; a corrected
  source yields a new fixture snapshot and never silently rewrites a released
  message-set version or regenerates its messages.
- **TSD-015 proxy labels and TSD-018 baseline:** synthetic interaction or
  complaint fields derive a `FixtureProxyLabelRow` (e.g. `was_resolved` or
  `sla_breached`) and a small `FixtureBaselineCell` stand-in. These are not
  classifier `GoldLabels`, which come from the separate team-authored
  synthetic messages (decision 16). The fixture does not recalculate or
  replace the `[measured]` TSD-018 report.
- **T-407 reviewed decisions:** the evidence stand-in identifies which
  fixture-derived facts would need fresh review. A human-reviewed decision or
  sign-off is never rewritten here; T-407 consumes the resulting lineage and
  decides whether new review is required.

T-103 and T-106 are interface-only dependencies: the fixture imports
`calvino.data.splits.assign_record` read-only and observes their label and
frozen-test boundaries. It does not change their implementations. T-407 and
T-408 are consumers, not dependencies or interfaces designed by this spec.

## Inputs and outputs

**Inputs**

- Small synthetic source revisions partitioned by `process_date`.
- The table and lineage conventions documented in TSD-007, plus T-103's
  customer-bucket and event-date split rule.
- A fixture manifest identifying T-103 test-split fixture records and a
  fixture row marked `frozen_suite_sentinel: true`, representing the T-303
  suite boundary without claiming that a source record exists in its
  hand-written cases. No real customer, account, case, or transaction ids.

**Outputs**

- `tests/fixtures/freshness/`: labelled synthetic source revisions, a frozen
  membership manifest, and fixture-local derived label/evidence expectations.
- `src/calvino/data/freshness.py`: the public API for artifact lineage,
  freshness checks, update planning/application, and deterministic reports.
- `src/calvino/data/freshness_models.py`: immutable lineage/revision records,
  validation, canonical hashing, and JSONL parsing.
- `src/calvino/data/freshness_snapshot.py`: source-kind/process-date
  partitioning and fixture snapshot construction.
- Offline tests under `tests/calvino/data/` proving exact before/after changes,
  stale-artifact rejection, and frozen-set isolation.
- An update to DESIGN.md 8.2 documenting the agreed window, quarantine, and
  frozen-set handling rule in the implementation change.

## Approved defaults

- **P1 — late-partition window: 30 calendar days, inclusive [hypothesis].**
  This is an unmeasured fixture default; DATA.md documents late partitions but
  no measured arrival lag. For a first-seen partition, compare `arrival_date`
  to `process_date`: day 0 and day 30 are accepted; day 31 is quarantined.
  A quarantined first-seen partition is reported and makes the dataset not
  current to the latest observed input.
  Corrections to an already accepted source record are exempt from this
  first-seen late-partition window, even if they arrive months later; they
  follow revision ordering and split/frozen-set rules instead. Revisions to a
  first-seen partition whose initial revision was quarantined do not qualify
  for the correction exemption; they remain quarantined until a new accepted
  snapshot or a maintainer waiver recorded in the fixture manifest. A
  correction that fails source-contract validation is quarantined regardless
  of age: keep derived outputs at the last accepted revision, report
  `pending_quarantined_correction`, and mark the dataset as not current to the
  latest observed revision. An `arrival_date` before `process_date` is invalid.
  Arrival dates are fixed fixture inputs, never read from the system clock.
  Clearing a pending quarantine with a later accepted snapshot or manifest
  waiver is outside T-105; until then, the status remains pending, not current.
- **P2 — revision ordering and idempotence.** Each source record has a
  strictly increasing `revision_no`. The highest accepted revision is current.
  Re-ingesting the same revision number and identical content is an idempotent
  no-op: it changes or invalidates no artifacts. The same revision number
  with different content is invalid, fails closed, and is reported as a
  pending quarantined correction. A lower revision
  arriving after a higher accepted revision is recorded as `superseded`, does
  not replace the current source, and changes or invalidates no derived output.
  Its observed revision/file digest is retained in the revision ledger, but
  the accepted partition snapshot and its hash remain unchanged.
- **P3 — split reassignment after correction.** Call the existing
  `calvino.data.splits.assign_record(customer_id, event_date)`; do not
  reimplement hashing or window rules. A record that qualifies for a different
  non-frozen split, including train-to-calibration, is removed from its old
  outputs and included in rebuilt outputs for the new split. A bucket/date
  mismatch or pilot record remains excluded as T-103 specifies. Any move into
  or out of frozen territory follows P4.
- **P4 — frozen-set drift, before source quarantine.** The frozen set is the
  union of the T-103 test split and the T-303 suite. For any highest revision
  with enough parseable fixture identity/date fields to evaluate membership,
  if a correction touches a frozen record, changes its customer/date so that
  it would enter or leave the frozen set, a late first-seen record would enter
  it, or a fixture row carries the T-303 sentinel flag, append an immutable
  source-revision lineage record and report `frozen-set drift detected`, even
  if the revision is outside the
  P1 window or fails source-contract validation. New values from a drift
  revision are never admitted to frozen or mutable accepted snapshots. Do not
  rebuild, retrain on, or alter frozen artifacts or membership. If a formerly
  non-frozen record would enter the frozen test split, invalidate and remove
  its old outputs
  from every non-frozen split so the same record cannot remain in train and
  test. Do not add it to the frozen test outputs. Removing that row changes
  the accepted non-frozen partition file hash and invalidates every descendant
  from that
  partition; this does not change the frozen partition hash. If a frozen
  record would move to a non-frozen split, keep the frozen version unchanged
  and do not add it to that split. This rule takes precedence over P1 and P3;
  also report a pending quarantine reason when applicable. A maintainer may
  later authorize a new set version;
  creating or evaluating that version is outside T-105. The latest-observed
  snapshot is not current while this drift is unresolved; the previous
  accepted snapshot remains selectable as historical only. Frozen artifacts
  are checked against the initial accepted snapshot's partition hashes and
  contract versions, never against changed latest-source hashes or the latest
  policy contract. A stale frozen artifact is retained unchanged, listed as
  blocked, and makes the overall dataset not current. When a
  frozen-drift record was previously accepted in a non-frozen partition, its
  removal changes that non-frozen partition's accepted hash and invalidates
  every descendant; it never changes the frozen partition hash. A new
  day-31 first-seen record that would enter frozen territory reports both
  `late_window` and `frozen_set_entered` reasons and changes no accepted
  partition hash.
- **P5 — one lineage representation.** Add the small
  `calvino.data.freshness` helper as the canonical runtime representation for
  per-artifact lineage. The existing `contracts/data/lineage.json` remains the
  TSD-007 source-to-pipeline step inventory; it is not a per-artifact record
  and will not be copied into a second fixture-specific format. The helper
  records each artifact's stable id and kind, parent artifact ids, source
  SHA-256 values, referenced contract versions, and producer commit. Tests use
  the fixed literal `fixture-commit-v1` for that field; they never call
  `git rev-parse` or read the current repository commit.

These defaults are for the synthetic proof. P1 does not establish a production
retention or ingestion service-level objective.

## Interfaces

### Artifact lineage

`calvino.data.freshness` owns one immutable `ArtifactLineage` representation
shared by source partitions, fixture-derived labels, and candidate-evidence
stand-ins. Each record includes:

- `artifact_id` and `artifact_kind`;
- parent artifact ids, if any;
- source identifiers mapped to SHA-256 digests;
- referenced contract/interface versions; and
- the producing git commit.

The fixture uses this same record at every layer. It must not invent separate
lineage shapes for labels or evidence. Source identifiers are fixture-local
names, not storage paths or live dataset locations.

### Python API

`calvino.data.freshness` provides these fixture-scoped interfaces:

- `ArtifactLineage` (frozen dataclass): the fields listed above. Source hashes
  are lowercase SHA-256 hex digests; contract versions and parent ids are
  explicit, sorted tuples for deterministic serialization. Source hashes name
  the whole resolved, accepted `process_date` partition file, not only the
  corrected row or the raw revision-arrival envelope. Any accepted changed row
  therefore invalidates every derived artifact depending on that partition;
  the report distinguishes invalidated/rebuilt ids from semantic row values
  that actually changed. Quarantined or superseded revisions do not change
  the accepted partition hash.
- `SourceRevision`: stable fixture record id, monotonic `revision_no`,
  observed source-file id and SHA-256, row SHA-256, `process_date`, fixed
  `arrival_date`, synthetic `customer_id`, `country_variant` (MX/CO/AR), and
  event date. The accepted partition file is deterministically materialized
  from highest accepted revisions.
- `RevisionStatus`: a record with one `disposition` (`accepted`,
  `quarantined_late`, `quarantined_invalid_correction`, `superseded`, or
  `frozen_drift`) and a sorted tuple of zero or more `reasons` (for example
  `late_window`, `contract_invalid`, `frozen_set_entered`, or
  `lower_revision`), plus the observed `source_file_id` and
  `source_file_sha256`. A day-31 revision entering frozen territory has
  disposition `frozen_drift` and both `late_window` and
  `frozen_set_entered` reasons.
- `FreshnessReport`: deterministic collections of revision statuses,
  pending-correction ids, rebuilt/invalidated artifacts, changed/unchanged
  seed facts, proxy labels, baseline cells, changed/unchanged evidence,
  blocked frozen-artifact ids, and frozen-set drift ids.
  `is_current_to_latest_observed` is false while any quarantine, frozen drift,
  or stale frozen artifact is unresolved. A later accepted snapshot or manifest waiver may clear
  the flag, but defining that resolution flow is outside T-105. It does not
  estimate hypothetical label/evidence changes for an unauthorized frozen-set
  version.
  A revision's single disposition never hides additional reason codes.
- `FixtureSeedFactRow`: synthetic `seed_id`, source record id, split,
  decimal-string `amount`, currency, `amount_band`, `policy_version`, fixture-only
  `expected_outcome: ExpectedOutcome` from `calvino.evaluation.oracle`, and
  lineage id.
- `FixtureProxyLabelRow`: label id, source record id, proxy label name/value,
  split, and lineage id; it is explicitly distinct from `GoldLabels`.
- `FixtureBaselineCell`: cell id, proxy label name, numerator, denominator,
  and lineage id.
- `CandidateEvidenceRow`: `evidence_id`, sorted `source_record_ids`,
  source-derived seed/proxy artifact ids, `evidence_digest`, and `lineage_id`.
  This is a fixture stand-in only, not a candidate schema, human-reviewed
  decision, promotion decision, metric, or scorecard.
- `check_artifact_freshness(artifact_id, lineage_by_id,
  source_hashes_for_selected_snapshot, current_contract_versions) -> None`:
  validates the artifact and its ancestors against the explicitly selected
  source snapshot (the accepted mutable snapshot, or the frozen manifest's
  original snapshot); raises
  `StaleArtifactError` if any recorded source hash or contract version is
  missing or differs from that snapshot, or if an ancestor is stale. A
  quarantined correction is reported separately and prevents the overall
  dataset from being marked current; the accepted snapshot's artifacts remain
  available explicitly as that prior version.
- `plan_revision_update(revisions, lineage_by_id, accepted_revisions,
  frozen_members) -> UpdatePlan`: deterministically identifies accepted,
  quarantined, superseded, pending-correction, and frozen-drift ids plus the
  affected dependency closure. It does not mutate inputs.
- `apply_revision_update(plan, initial_state, output_dir) -> FreshnessReport`:
  rebuilds affected non-frozen fixture artifacts in the caller-provided
  temporary output directory and returns the exact before/after diff. The
  initial accepted state supplies the immutable frozen artifacts for comparison
  and reuse; a changed policy contract marks affected frozen artifacts blocked
  rather than rebuilding them. It also drops/invalidate prior non-frozen outputs for a source record
  newly classified into frozen territory, without changing frozen outputs.

These functions are fixture support, not a general production ingestion API.
They do not import, modify, or prescribe interfaces for T-407 or T-408.

### Freshness and update report

The helper exposes deterministic operations to validate lineage, compute the
affected dependency closure, and produce a `FreshnessReport`. The report names
the exact synthetic ids for:

- accepted and quarantined input revisions;
- rebuilt and invalidated artifacts;
- changed and unchanged derived-label rows;
- changed and unchanged candidate-evidence rows; and
- frozen-set drift, including the frozen artifacts and label/evidence ids that
  were blocked from change. The report does not estimate a future, separately
  authorized set version.

Freshness is computed, not stored: an artifact is stale for a selected accepted
snapshot if any source SHA-256 or referenced contract version in its lineage
differs from that snapshot. Staleness propagates to every descendant that
depends on that artifact. Reusing an artifact stale for the selected snapshot
raises `StaleArtifactError`; it never warns, falls back, or silently treats the
artifact as current. If a source later returns to an earlier accepted hash,
the matching prior artifact is fresh again when its contract versions and
ancestors also match. The producer commit is recorded for traceability but,
by itself, does not make an otherwise-current artifact stale.

For a quarantined correction, outputs remain tied to the last accepted source
snapshot. The report marks `pending_quarantined_correction` and states that the
overall dataset is not current to the latest observed revision. The last
accepted outputs may only be read when the caller explicitly selects that
accepted snapshot; they are not silently presented as current to the latest
input. No derived output is built from the quarantined revision.

The helper rebuilds affected non-frozen fixture outputs from current accepted
inputs and retains prior artifact versions for audit in the temporary test
output. It does not persist a `stale` flag; staleness is recomputed against the
selected snapshot. The implementation does not delete unrelated files or
mutate the committed fixture.

## Correction and split behavior

Each synthetic source row has a stable fixture id, `customer_id`, event date,
`process_date`, and monotonic source revision. A correction is a higher-numbered
source revision for the same fixture id; a late record is a first-seen id whose
`process_date` precedes its arrival date.

For an accepted, non-frozen correction:

1. hash the new source revision and compare it with the recorded lineage;
2. recompute the row's T-103 split using the corrected `customer_id` and event
   date;
3. invalidate the old partition-derived labels and evidence that depend on the
   changed source or split;
4. rebuild only affected non-frozen outputs; and
5. report the exact changed ids and source/contract versions.

If a correction removes a row from train, the old training-derived labels and
evidence are invalidated before any candidate output can be reused. If the row
qualifies for another non-frozen split, including calibration, it is moved
there and that split's dependent outputs are rebuilt. A bucket/date mismatch
or pilot row remains excluded. If the row would enter or leave frozen
territory, P4 applies: remove/invalidate any old non-frozen outputs that could
leak the record, but do not change frozen outputs or membership.

## Fixture and safety constraints

- Keep the fixture small and synthetic under `tests/fixtures/freshness/`.
- Use synthetic customer and record ids only; include MX/CO/AR examples and
  MXN/COP/ARS/USD currencies. Do not include BRL or Brazilian customers.
- Label the fixture README and files as synthetic. Do not copy live rows, names,
  ids, paths, or credentials.
- Tests run offline with no network, model provider, GPU, or real dataset.
- Store generated intermediate artifacts only in test temporary directories.
- Do not alter T-103/T-106 splits, labels, rubrics, message sets, or frozen
  T-303 cases.

## Required fixture matrix

Every row uses invented ids and fixed arrival dates. Together the rows must
cover:

| Case | Required synthetic condition |
|---|---|
| First-seen arrival boundary | Same partition shape arriving on day 0, day 30, and day 31 after `process_date`; first two accepted, day 31 quarantined |
| Late revision of quarantined source | A higher revision for a day-31-quarantined first-seen partition remains quarantined; it does not acquire the accepted-correction exemption |
| Delayed valid correction | Higher `revision_no` correcting an accepted row months after its original arrival; accepted because corrections are exempt from P1 |
| Duplicate and out-of-order revisions | Identical current revision re-ingested as a no-op; a lower revision arriving later recorded as superseded |
| Value-only amount correction | Same synthetic customer/date, `USD 350` to `USD 700` under the fixture's `policy/v2.yaml` gate; `amount_band`, fixture expected outcome, and dependent evidence change without placing a fixture value near the gate or above the hard-rule amount limit |
| Proxy-label/baseline correction | A synthetic `was_resolved` or `sla_breached` value changes; rebuild the corresponding fixture proxy-label row and baseline-cell stand-in, while leaving the committed measured TSD-018 report untouched |
| Customer-id correction | A changed customer hash bucket moves a record from train to calibration; old train outputs are removed and calibration outputs rebuilt using `assign_record` |
| Event-date correction | Recompute T-103 membership from the corrected date, including a pilot-window exclusion |
| Move into frozen territory | Correct customer/date so `assign_record` would return test (customer bucket ≥85 and event date ≥2026-01-01); invalidate/remove all prior non-frozen outputs, report drift, and leave frozen test membership/artifact bytes unchanged |
| Late frozen entry | A day-31 first-seen record that would qualify for test reports both `late_window` and `frozen_set_entered`; it changes no accepted partition hash |
| Move out of frozen territory | A frozen test member would qualify for a non-frozen split after correction; report drift and do not add it to that split or mutate its frozen artifacts |
| T-303 sentinel | A synthetic source row marked `frozen_suite_sentinel: true`; prove the flag reports drift without asserting that T-303 cases have source-record ids |
| Invalid arrival and pilot | `arrival_date` before `process_date` fails validation; a T-103 pilot-window row is excluded |
| Country/currency coverage | At least one synthetic record each for MX, CO, and AR; cover MXN, COP, ARS, and USD across fixture rows; no BRL or Brazilian customer |

## Tests

Tests use the committed synthetic fixture and temporary output directories.
The fixture matrix above is normative, not illustrative:

1. Identical inputs, policy/contract versions, and the fixed producer-commit
   literal `fixture-commit-v1` produce byte-identical lineage and reports.
   Tests never call `git rev-parse`.
2. First-seen day-0/day-30 partitions are accepted; day 31 is quarantined.
   A correction that fails source-contract validation keeps outputs at the
   last accepted revision, reports `pending_quarantined_correction`, and marks
   the overall snapshot not current to the latest observed source.
3. A correction arriving months after its first accepted revision is allowed
   by P1. A duplicate identical revision is a no-op; a lower revision arriving
   after a higher accepted revision is superseded and changes nothing. The same
   revision number with different content is quarantined and marks a pending
   correction.
4. A correction from USD 350 to USD 700 recomputes `amount_band` using
   `policy/v2.yaml`, changes the fixture expected outcome and exact dependent
   evidence, and records the canonical gate-table digest/version.
5. A proxy-source correction changes the exact fixture proxy-label and
   baseline-cell values and their dependent evidence, without touching the
   committed TSD-018 report.
6. A source partition file hash change invalidates every descendant derived
   from that partition, even if a row's semantic value is unchanged. The
   before/after diff separately identifies invalidated/rebuilt artifacts and
   seed facts, proxy labels, baseline cells, and evidence whose values actually
   changed versus stayed unchanged.
7. Any artifact stale under the selected accepted snapshot raises
   `StaleArtifactError`; no prior value is silently reused. If a source later
   reverts to a prior accepted hash with matching contract versions and
   ancestors, the prior artifact is fresh again.
8. A correction that moves a record from train to calibration removes it from
   old train outputs and rebuilds calibration outputs using
   `calvino.data.splits.assign_record`. Bucket/date mismatches and pilot rows
   are removed from their prior split outputs and stay excluded.
9. A former train record corrected into frozen test territory is removed from
   train outputs to prevent train/test leakage, while frozen test membership
   and artifact bytes remain unchanged. A frozen record corrected out of test
   is not added to any non-frozen split. Both cases report drift and append
   revision lineage.
10. A record marked `frozen_suite_sentinel: true` reports frozen drift without
   asserting source-record ids exist in T-303's hand-written cases.
11. Invalid `arrival_date`, malformed digests, and unknown parent artifact ids
    fail closed with actionable errors.
12. The fixture test verifies MX, CO, and AR coverage and MXN, COP, ARS, and
    USD currencies, while rejecting any BRL or Brazilian-customer fixture row.
13. A day-31 first-seen revision that would enter frozen test territory has
    disposition `frozen_drift` and both `late_window` and
    `frozen_set_entered` reasons; it changes no accepted partition hash.
14. A higher revision of a day-31-quarantined first-seen partition remains
    quarantined and pending; it does not inherit the correction exemption.
15. Changing only a referenced contract version makes the selected artifact
    stale and raises `StaleArtifactError`, even when source hashes are
    unchanged.
16. When an accepted train record is corrected into frozen test territory,
    removing it changes the accepted non-frozen partition hash and invalidates
    all descendants, while the frozen partition hash and frozen artifacts
    remain unchanged.
## Non-goals

- Continuous ingestion, a scheduler, a production reprocessing window, or live
  data access.
- Defining T-407/T-408 APIs, candidate schemas, metrics, scorecards, or
  promotion decisions.
- Retraining, recalibration, candidate evaluation, or automated promotion.
- Changing existing T-103/T-106 interfaces or the frozen T-303 evaluation set.

## Commit plan

**Spec-only review commit (completed):**

1. **`docs(data): specify T-105 freshness fixture`** — add this TSD-021,
   index it, link it from the T-105 card, and record the proposed scope in
   CHANGELOG.md. No code or fixture behavior was implemented in that commit.
   The maintainer approved the spec before implementation began.

**Implementation commits (merged in #81):**

1. **`feat(data): add freshness lineage models and fixture`** — add strict
   immutable revision/lineage types and the labelled synthetic fixture.
2. **`feat(data): build freshness fixture snapshots`** — materialize source-
   kind/process-date partitions and deterministic fixture-derived outputs.
3. **`feat(data): enforce freshness and revision handling`** — implement
   stale-artifact checks, update planning/application, revision ordering,
   quarantine, split reassignment, and frozen-set protection.
4. **`test(data): cover freshness update safety`** — verify exact update
   diffs, rejected revision provenance, and frozen artifact immutability.
5. **`docs(data): document freshness handling`** — describe the fixture-only
   rule in DESIGN.md 8.2 and update the task, handoff, and changelog. The full
   lint, format, Python test, and git-rule checks pass.

## Acceptance criteria

- The fixture proves lineage from source hash and contract version through
  affected partition, label, and candidate-evidence rows.
- Accepted changes rebuild only affected non-frozen artifacts. Any stale
  artifact raises on reuse.
- The before/after test identifies exactly which labels and evidence rows
  changed and which did not.
- Quarantined inputs remain visible as pending and never make old outputs
  appear current to the latest observed revision.
- Frozen test/T-303 membership and artifacts remain unchanged; drift is
  explicit and no frozen record leaks into training.
- The window and quarantine behavior are deterministic and tested at the
  boundary.
- DESIGN.md 8.2 documents the agreed handling rule without claiming
  production ingestion.
- All tests run offline using synthetic data only.
