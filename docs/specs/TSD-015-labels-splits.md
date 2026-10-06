# TSD-015: Labels, splits and gold-set rubric (T-103)

| | |
|---|---|
| Status | implemented for T-103; human gold annotation is T-107 (scope amendment accepted 2026-10-05) |
| Branch | `feat/labels-splits` |
| Depends on | T-101 (workflow choice); TSD-007 (data contracts); DATA.md findings |
| Required by | T-106 (message set); T-201 (calibration); T-303 (evaluation) |
| References | DESIGN.md 4.3, 5.1, 6.1, 7; decisions 16, 17, 22, 25; T-103 task card |

## Purpose and boundary

Define what the classifiers learn to predict, on which records, in which
split, and how the hand-labelled gold set judges them. Classifier text
itself is team-generated under T-106 (decision 16); this spec defines the
labels that text carries and the splits its seed records come from.

T-103 stays standalone: a proposal to merge it into T-106 was rejected.
T-103 is unblocked and T-106 is blocked on LLM keys, so waiting would stall
the evaluation path. The boundary is: T-103 owns label definitions,
customer and time splits, the five leakage rules, and the gold rubric with
the first-50 sheet. The oracle table, the generation prompts, the message
set and its datasheet belong to T-106's future spec, which references the
rules written here.

## Proposed defaults

Each item below resolves one open ambiguity. Every one is marked
**proposed — maintainer confirms at spec review**, and the implementation
PR changes nothing marked this way without a new entry here.

- **P1 — customer identity key (proposed — maintainer confirms at spec
  review).** The split key is the plain `customer_id`, shared across the
  four tables in scope (`call_center_interactions`, `call_transcripts`,
  `transactions`, `complaints`). No cross-table join is trusted as evidence
  (DATA.md: call-to-transaction links are at chance); the shared key is used
  only to keep one customer out of two splits, never to attribute a call to
  a transaction.
- **P2 — time split (proposed — maintainer confirms at spec review).** Train
  on the earlier window, test on the later window; the pilot window
  (17–30 June 2023) is pinned dev-only. Exact cutoffs are in
  [Time split](#time-split).
- **P3 — class balance (proposed — maintainer confirms at spec review).**
  Test and calibration keep natural rates, so every reported figure reads
  against the population the system will meet. Train may use a documented
  sampling strategy (stratified sampling or class weights); the strategy and
  the resulting mix are recorded in the training report, never silently.
- **P4 — T-103 / T-106 boundary (proposed — maintainer confirms at spec
  review).** As in [Purpose and boundary](#purpose-and-boundary): labels,
  splits, leakage rules, rubric and first-50 sheet here; oracle table and
  generation prompts in T-106's spec.
- **P5 — gold workforce (accepted; T-107 provenance amendment accepted 2026-10-05).**
  The maintainer enters or explicitly approves the final labels for the
  first 50, with no second annotator. Under the accepted T-107 amendment,
  disclosed model proposals may inform classifier labels only. The 18
  existing labels are maintainer-only; 32 proposals were seen before
  review, so reports state that Claude Sonnet 5.5 (`claude-sonnet-5-5`)
  drafted them in Claude Code on 2026-10-05, plus the anchoring risk.
  Oracle facts and human outcomes are model-drafted with the drafter
  named and maintainer-reviewed (decision 48). The
  same rubric version scales to the 150–300 DESIGN-7 set.
- **P6 — leakage rules home (proposed — maintainer confirms at spec
  review).** All five rules are worded and tested under T-103; T-106's spec
  references them and runs them over its registries.

## Label definitions

The labels follow Laya's questions in DESIGN 6.1, restated here so the
rubric has one source:

| Question | Labels |
|---|---|
| Workflow area | stuck payment · dispute or unrecognised charge · fraud or stolen access · other banking · out of scope; unset for unclassifiable messages |
| Intent within a stuck payment | status · cancel · retry · open a case · case status · talk to a person |
| Clear enough to act on | yes · no (two options, neutral keys) |
| Needs a person | yes · no (two options, neutral keys) |
| Injection or manipulation | yes · no (two options, neutral keys) |

Boundary cases, from DESIGN 6.1 and the September planning draft:

- Unrecognised charges, disputes and fraud signals go to a person; only the
  stuck-payment intents above may resolve automatically.
- An exchange-rate discrepancy on a foreign payment is clarify, not fraud.
- A hostile message about a trivial fee is no escalation on insults alone;
  tone never flips needs-a-person without a qualifying intent.
- Empty, emoji-only or garbled messages are clarify or refuse, never guess
  (clear-enough = no).
- Anything outside the workflow gets the honest out-of-scope reply with a
  path to a person; no agent starts.

## Proxy mapping

Dataset fields supply proxy outcomes for the human baseline only. They show
what agents *did*, not what was *needed* (DESIGN 7):

| Proxy label | Source field |
|---|---|
| Resolved | `call_center_interactions.was_resolved` |
| Escalated | `call_center_interactions.was_escalated` |
| Follow-up needed | `call_center_interactions.requires_followup` |
| Problem transaction | `transactions.transaction_status` in Declined, Pending, Reversed |
| Investigation outcome | `complaints.status`, `sla_breached`, `resolution_days`, `compensation_granted` |

Proxies are never classifier targets. Classifiers train and evaluate on the
team-generated message set, whose labels come from the rubric above
(decision 16). Agreement between proxy and gold labels is reported with the
baseline, so a reader can see where human practice and the rubric diverge.

## Customer split

Each `customer_id` belongs to exactly one split, by a stable hash, so the
assignment is reproducible with no lookup table:

```
bucket = int(sha256(customer_id_hexdigest)[0:8], 16) % 100
bucket 0–69   -> train          (~70%)
bucket 70–84  -> calibration    (~15%)
bucket 85–99  -> test           (~15%, frozen)
```

Shares are `[hypothesis]` on uniform customer volume; the implementation
reports the achieved shares. Group attributes (country, segment, dialect)
are never split inputs (decision 25); fairness slices are measured after
the fact, and cells under 30 cases are flagged, not failed.

## Time split

**Proposed — maintainer confirms at spec review.** Event dates are the
per-table event/partition dates named by the TSD-007 contracts (partition
`process_date` where present); the implementation PR names the exact column
per table rather than guessing here.

| Window | Dates | Use |
|---|---|---|
| Pilot (dev-only) | 2023-06-17 – 2023-06-30 | fixtures, debugging, scenario drafting; never in a published figure |
| Train | event date < 2025-06-01 | classifier training (bulk past, ~2 of 3 years) |
| Calibration | 2025-06-01 – 2025-12-31 | temperatures and thresholds; recent enough to see drift, sealed off from the frozen set |
| Test (frozen) | event date >= 2026-01-01 | held-out evaluation only; never enters training, calibration or the flywheel |

Justification `[hypothesis]`: the cutoffs are date-defined, not
row-fractioned, so they survive volume skew; the most recent six months
measure current performance (about one sixth of 686,296 calls and 67,095
complaints under near-uniform volume — to be confirmed at implementation);
the calibration band sits between train and test so tuning sees drift
without touching the frozen set. Portuguese evaluation uses the same
windows on synthetic text only, under stricter thresholds until measured
(decision 22).

A record is usable in a split only when its customer bucket *and* its event
date agree on that split; out-of-window records are excluded from
classifier work (documented loss, counted in the split report). Test and
calibration keep natural rates (P3); train may resample with documentation.

## Leakage rules

The five rules, each with a test in `tests/calvino/data/test_leakage.py`.
T-106 references them by id and runs them over its seed registries.

- **L1 — customer isolation.** No `customer_id` appears in more than one of
  train, calibration, test or gold. Test: pairwise intersections of the
  final assignments are empty.
- **L2 — time order.** No train record is dated at or after the calibration
  window start; no train or calibration record is dated at or after the
  test window start. Test: per-split maximum event date below the bound.
- **L3 — dataset text never trains.** No value from
  `call_transcripts.customer_text` / `agent_text` (42 fixed templates) or
  `complaints.description` (5 fixed texts) appears in any classifier input.
  Test: an exact-match scan of built inputs against the template texts, plus
  an allowlist test that message text may only enter through team-generated
  sources.
- **L4 — generation isolation.** Train and test messages come from disjoint
  seed-record sets under separate prompts; no seed key feeds both sides.
  T-103 ships the seed-registry schema and the disjointness check (tested on
  synthetic seeds); T-106 executes it on the real registries, including the
  adversarial and hand-written test subsets.
- **L5 — gold stays held out.** Gold customer and seed keys are excluded from
  train and calibration; gold is used only for oracle/judge agreement and
  final reporting. Test: intersection of the gold key set with the
  train/calibration key sets is empty.

## Gold rubric, adjudication, agreement

The rubric is versioned (`gold/rubric-v1.md`): one file holding the label
tables above, the boundary cases, worked examples per intent, and the rule
that an unclear case is flagged for the maintainer, never guessed. Every
gold record names its rubric version; a rubric change mints a new version
and re-labels only the affected records.

Adjudication with a single annotator (P5) means no inter-annotator vote:
quality control is the oracle-vs-gold disagreement review. Every
disagreement is read and classified as rubric gap, oracle bug or label slip
and logged; rubric gaps amend the rubric as a new version. The oracle's own
error is bounded by this agreement and reported alongside every score that
uses the oracle (DESIGN 7).

Agreement metric: per-question exact agreement plus Cohen's kappa on
needs-a-person and on oracle outcome vs gold outcome, each with n and a
note that n=50 gives wide intervals. At this size the numbers are
descriptive; no promotion gate reads them until the 150–300 set lands.

### Amendment proposal (2026-10-04): gold outcome consistency report

This amendment adds optional fields to the existing `GoldRecord` schema;
it does not change or invalidate any of the current 50 rows. The reason,
scope and implementation contract are specified in
[TSD-019](TSD-019-message-set.md#t-103-gold-annotation-and-agreement-report).
This is a single-annotator consistency check, not an independent gold
benchmark or inter-annotator study.

The rows currently use `seed_ref: "hand-written"` and have no actual bank
record. The maintainer therefore assigns **nominal scenario facts**, not
facts claimed to come from the dataset: status, owner, amount band and
fraud flag. The annotation sheet presents the customer message and those
raw nominal facts first. The maintainer records them before the
message-judgement fields (`intent`, `ambiguous`, `in_scope`) and before
seeing any oracle outcome. The maintainer then records the
rubric-based human outcome without viewing the oracle result. The
`oracle_facts` are evaluated by the existing TSD-013 table; the resulting
comparison measures consistency between the maintainer's rule
application and that hand-written table. It does **not** establish the
table's agreement with real-world outcomes.

The scope of this descriptive check is only the TSD-013 oracle table under
the recorded nominal facts. It does not bound T-106's brief-derived
defaults, the correctness of message-set labels, or model performance.
The report must state the single annotator and `scored n/50` beside every
agreement value; `n` is the number of complete, valid reviewed rows, not
the whole sheet by implication.

Annotation is phased to make the maintainer workload explicit:

1. Complete the existing message labels: 18/50 are already labelled, so
   32 rows remain.
2. For all 50 rows, add four nominal raw facts, three
   message-judgement facts, and one human outcome: 8 annotation fields per
   row, 400 field entries total. The separate T-106 P4 review cap of 170
   verdicts does not include or replace this work.

The implementation supplies blank annotation/fact sheets and validation,
not suggested or generated values. Reports show `scored n/50`, completeness
counts and reasons for unscored rows, so a reviewer who completes easier
rows first cannot hide the selection from readers.

## First-50 sampling plan and record format

Stratified over intent and variant, with the remainder spent on the cases
most likely to break the policy: 6 stuck intents × 3 country variants
(MX, CO, AR) × 2 = 36, plus 14 boundary/adversarial (hostile-but-trivial,
empty/emoji/garbled, exchange-rate discrepancy, injection attempt,
dispute-or-fraud to a person, out-of-scope). Seeds come from test-window
records or are hand-written; every message is team-written or
team-reviewed, labelled synthetic.

One JSONL record per gold case in `tests/fixtures/gold/gold-050.jsonl`:

```
gold_id, rubric_version, message, language_variant, seed_ref (table + key,
or "hand-written"), labels {workflow_area, stuck_intent, clear_enough,
needs_person, injection}, optional oracle_facts, optional human_outcome,
optional outcome_annotator, optional outcome_labelled_at, annotator,
labelled_at, notes
```

No customer records, no dataset text: the file holds only team-generated
messages and is safe to commit. All four new fields are optional and
default empty, so the existing 50 rows continue to validate. `oracle_facts`
must use TSD-013's `INTENTS` and `AMOUNT_BANDS`; only `status` is nullable.
`human_outcome` must be a TSD-013 `ExpectedOutcome` other than `ERROR`,
which the oracle table never produces. Outcome provenance uses
`outcome_annotator` and `outcome_labelled_at`; it is not inferred from the
existing label annotator fields.

## File locations and check commands

Implementation (a later PR, after this spec is approved) creates:

- `src/calvino/data/splits.py` — hash assignment, windows, split builder,
  split report with shares and exclusion counts
- `src/calvino/data/labels.py` — label enums, proxy mapping, rubric helpers
- `gold/rubric-v1.md` — the versioned rubric
- `tests/calvino/data/test_splits.py`, `test_labels.py`,
  `test_leakage.py` (L1–L5) — synthetic fixtures only
- `tests/fixtures/gold/gold-050.jsonl` — the first-50 sheet

Checks:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest tests/calvino/data
bash tests/git/test_git_rules.sh
```

## Tests

Every test runs without network, GPU or the real dataset. Fixtures are
small, synthetic and labelled synthetic, using MX/CO/AR with MXN/COP/ARS/USD
only (DATA.md handling rules; never BRL). Coverage: hash determinism (same
id, same split, across processes), window boundaries inclusive/exclusive,
L1–L5 each failing on a crafted violation, proxy mapping on fixture rows,
gold record schema validation, and a scan test proving no fixture message
duplicates a dataset template shape.

## Done criteria

- Splits documented and reproducible: the same `customer_id` always lands in
  the same split, and the split report states shares, windows and exclusion
  counts.
- All five leakage tests pass; T-106's spec references L1–L5 by id.
- Rubric v1, gold schema and blank first-50 worksheet are committed.
  Maintainer annotation and the descriptive oracle-vs-human consistency
  report are owned by T-107.
- No dataset transcript used as model input anywhere in the path; no
  customer record committed.

## Scope amendment (accepted 2026-10-05): implementation and human review

T-103 is complete when its rubric, split implementation, leakage rules,
gold schema, validators, blank worksheet and reporting tools are
implemented. The maintainer's gold annotations and agreement report are
separate work tracked in [T-107](../tasks/T-107-gold-annotation.md).
This amendment does not change the rubric, schema, or required review
method below.

The current 50 gold rows are all `seed_ref: "hand-written"`; they do not
represent actual bank records. The maintainer assigns **nominal scenario
facts** (status, owner, amount band and fraud flag), not claims about the
dataset. To avoid circular review, the annotation sheet shows the message
and those raw facts first. The maintainer records those four fields before
the message-judgement fields (`intent`, `ambiguous`, `in_scope`), then
records the rubric-based outcome without viewing the oracle output. This
is a same-person consistency check between the maintainer's rule
application and the hand-written TSD-013 oracle table, not an independent
benchmark or inter-annotator study. The single annotator and `scored n/50`
must appear beside every reported agreement value.

The bound applies only to the TSD-013 oracle table evaluated on these
nominal scenario facts. It does not establish the correctness of
T-106's brief-derived defaults, T-106 message labels, or model predictions.
Disagreements are reviewed by the maintainer and classified as rubric gap,
oracle mapping bug or label slip.

Work is phased and explicit: 18 of the 50 existing classifier-label rows
are complete, leaving 32 rows. The separate oracle-consistency pass adds
eight fields per gold row (four nominal record facts, three
message-judgement facts, and one outcome), for 400 field entries across
the sheet. This work is in addition to T-106's separate 170-verdict review
cap. Reports state completeness counts and scored n/50 so an easy-first
review order is visible.

The schema change is additive. `oracle_facts`, `human_outcome`,
`outcome_annotator` and `outcome_labelled_at` are optional and default
empty, preserving validation of all existing rows under
`extra="forbid"`. When present, `oracle_facts.intent` must be a TSD-013
`INTENTS` value; `amount_band` must be an `AMOUNT_BANDS` value; only
`status` may be null. `human_outcome` must be a TSD-013
`ExpectedOutcome` other than `ERROR`. T-107 may use disclosed
model-drafted proposals for classifier labels only; each final classifier
label requires explicit maintainer review. The current proposals were
drafted with Claude Sonnet 5.5 (`claude-sonnet-5-5`) in Claude Code on
2026-10-05. They were seen before review, so the report must state the
anchoring risk. Model proposals must not be auto-filled into
`oracle_facts` or `human_outcome`; under decision 48 those fields may be
model-drafted with the drafter named in `outcome_annotator` and explicit
maintainer review.

The implementation adds:

- `src/calvino/data/labels.py`: optional typed fields and a completeness
  validator for outcome annotations.
- `tests/calvino/data/test_labels.py` and
  `tests/calvino/data/test_gold_agreement.py`: backward compatibility,
  enum/nullability validation, and report denominator/completeness cases.
- `docs/templates/T-103-gold-outcome-annotations.csv`: a blank annotation
  sheet containing the messages and blank fact/judgement/outcome fields,
  with columns ordered to enforce raw facts before message judgements.
- `scripts/report_gold_agreement.py`: validates rows, writes
  `reports/eval/T-103-gold-agreement.md` and
  `reports/eval/T-103-gold-disagreements.md`, states scored n/50, and
  never fills or suggests annotation values.

The report is descriptive. It lists unscored rows with reasons, displays
the oracle/human confusion matrix and agreement numerator/denominator,
reports kappa only when mathematically defined, and labels it
single-annotator consistency rather than independent validation.
