# TSD-019: Team-generated customer message set (T-106)

| | |
|---|---|
| Status | accepted — the maintainer accepted P1–P6 as written on 2026-10-05; the code is merged keyless (#74) |
| Branch | `feat/message-set` (the T-106 card says `data/message-set`; that type is rejected by the push hook, so `feat/` stands) |
| History | first drafted as `TSD-018-message-set.md` (never merged); renumbered to TSD-019 after TSD-018 was taken by the human-baseline spec |
| Depends on | T-103 / TSD-015 (labels, splits, L1–L5, rubric v1, gold sheet); TSD-013 (the oracle consumer) |
| Blocked by | LLM provider keys for the generation step only (decision 28); spec, tests and fixtures need no keys |
| Required by | T-201 (calibration), T-202 (fine-tuning), T-303 (evaluation) |
| References | decisions 16, 17, 22, 25, 28, 29; DESIGN.md 4.3, 5.1, 6.1, 7, 8.1; DATA.md; T-106 card |

## Purpose and boundary

Supply the customer text the classifiers are calibrated, fine-tuned and
evaluated on, because the dataset's transcripts are templated and carry no
label information (decision 16). The dataset supplies structured seed facts
and the human baseline; every message in this set is team-generated and
labelled synthetic.

Boundary with TSD-015 (P4 there): labels, splits, leakage rules, rubric and
gold sheet are TSD-015's; this spec owns the seed registries, the
brief→labels derivation table, the record-facts→oracle mapping, the two
generation prompts, the message files, the review log and the datasheet.
Boundary with TSD-013: the outcome oracle (`oracle_outcome` in
`calvino.evaluation`) already exists and is reused as is; this spec creates
**no competing oracle**, per the T-106 card. Boundary with TSD-018
(human baseline): TSD-018 measures category-level human
outcomes on the full live data; this spec generates synthetic classifier
text. Neither consumes the other's outputs: baseline aggregates never seed
messages, synthetic messages never enter the baseline, and complaint seeds
use complaint-record facts (status, SLA state, event date), never baseline
figures. Boundary with T-203: Portuguese is explicitly out of this spec
(see [Allowed languages](#allowed-languages)).

## Proposed defaults

Every item below resolves one open choice. Each is marked **proposed —
maintainer confirms at spec review**, and the implementation PR changes
nothing marked this way without a new entry here.

**Acceptance (2026-10-05).** The maintainer accepted P1–P6 as written, so
the "proposed" markers below record the original wording and the defaults
now stand. The optional second-label pass in P4 (a different-family model
over every row, the maintainer adjudicating disagreements only) is
recommended and planned. Open items that this acceptance does not close,
both the maintainer's: dataset access for the seed-drawing step (P2) and a
backup location for the secret salt (P3).

- **P1 — sizes and composition (proposed — maintainer confirms at spec
  review).** Train 600, calibration 240, test 300 (total 1,140), composed
  as follows. Train is drafted entirely with the plain train prompt (no
  adversarial styling): 450 stuck-intent (6 stuck intents × 3 country
  variants × 25 per cell), 90 non-stuck heads (dispute / fraud-report /
  out-of-scope × 3 variants × 10 per cell), and 60 injection positives in
  plain phrasing (ordinary-looking requests carrying injection content per
  rubric v1, 3 variants × 20). Adversarial *styling* stays confined to
  test per decision 16; the train/calibration injection positives exist so
  the classifiers see the positive class outside adversarial phrasing.
  Resampling is allowed on train only and is documented in the datasheet,
  never silent (TSD-015 P3). Calibration is 3 variants × 80 with a natural
  outcome mix inside each variant (each 80 is roughly 60 stuck at natural
  mix + 10 non-stuck heads + 10 injection positives, all plain-drafted, so
  per-variant calibration reads stay at or above decision 25's 30-case
  line). "Natural mix" means: within each seed kind, the
  Declined/Pending/Reversed status mix mirrors the usable seed pool's
  observed mix for that split; the split report states the pool mix and
  the drawn mix side by side so a skew is visible. Test is 240
  seed-generated (3 variants × 80: each 80 is roughly 60 stuck at
  natural mix + 10 non-stuck heads + 10 injection positives, mirroring
  the calibration shape, test prompt with disjoint style instructions)
  plus a 60-case supplement
  confined to test: ~40 adversarial rewordings (~10 wrong/missing-data,
  ~10 injection attempts, ~8 multilingual-ambiguity, ~12 DESIGN 6.1 edge
  cases: exchange-rate discrepancy, hostile-but-trivial tone,
  empty/emoji/garbled) and ~20 hand-written messages. The supplement is
  reported as its own slice; any reported slice under 30 cases is flagged,
  not failed (decision 25).
- **P2 — seed sourcing (proposed — maintainer confirms at spec
  review).** A candidate record is usable only when its customer bucket
  *and* its event date agree on one split (TSD-015 AND-condition).
  Implementation filters to usable records first, then samples to the P1
  composition — there is no fixed oversample factor to hit. The split
  report states considered, usable, drawn and excluded counts per split.
  Per-split yield reality: calibration and test pools are thin, so the
  implementation counts usable records per seed kind before drafting and
  flags complaint-seed tightness in the report (complaint seeds ground the
  open-a-case / case-status intents; quotas are never silently filled with
  other kinds).
- **P3 — secret salt per set version (proposed — maintainer confirms at
  spec review).** Committed registries carry seed *facts*, never records:
  no real `customer_id`, no transcript text, no complaint text (DATA.md:
  committed outputs are aggregates only, never records). Customer identity
  is stored as a truncated salted hash (`sha256(customer_id + salt)[:16]`,
  hex) — enough for the L1 equality check, not enough to identify anyone.
  The salt is SECRET and per set version: generated once (32 random bytes,
  hex), kept in the git-ignored `data/message-set-salt-v1` with
  local-user-only permissions, and never committed. The datasheet records
  the salt version only (`salt-v1`), never the value. `seed_key` is
  derived with the same salt (see [Seed keys](#seed-keys)). No
  rotating-per-run, no committed salt. The full seed_key → record pointer
  log lives in the git-ignored `data/` folder for regeneration and is
  never committed; losing the salt or the pointer log means the set cannot
  be regenerated, which the datasheet states.
- **P4 — weighted review (proposed — maintainer confirms at spec
  review).** The maintainer reviews a weighted sample per split against
  rubric v1 before the split is used: train ≥30 stratified across stuck
  intents, non-stuck heads and plain injection positives (for example 18
  stuck at 3 per intent + 6 non-stuck + 6 injection — never 5-per-stuck
  intent only, which would leave the positive class outside adversarial
  phrasing unreviewed), calibration ≥50, test ≥30 from the base slice
  plus all ~40 adversarial rewordings plus all ~20 hand-written rows
  (about 90 test rows; no machine-check escape hatch — every adversarial
  row is reviewer-read). The written accept rule: a split (or prompt
  version) is accepted iff its reviewed sample carries **≤1 defect** (a
  defect is a fail verdict or a row needing label correction at
  review); 2+ defects, or the same defect twice, is a systematic failure
  and mints a new prompt version plus a fresh review sample. Reviewed
  messages are never silently edited into passing — corrections are
  logged per row with reviewer and reason. The minimums sum to about
  170 reviewed verdicts per set version (30 train + 50 calibration +
  ~90 test), capped at 170: the cap is set by maintainer review budget,
  not by any figure from a previous audit. An optional second-label pass
  runs a different-family model over all rows (keyed; about 1,140 calls
  per set version); the maintainer adjudicates disagreements only, and
  every disagreement is logged as rubric gap, model slip or reviewer
  slip.
- **P5 — file home (proposed — maintainer confirms at spec review).**
  Versioned files under `evaluation/message-set/v1/` (see [File
  locations](#file-locations-and-check-commands)); code in
  `src/calvino/data/message_set.py` with tests in
  `tests/calvino/data/test_message_set.py`. Implementation commits are
  planned around the size limits: one commit per JSONL file (three
  registries plus three message files), prompts/loader/generator/tests in
  small commits, review log and datasheet last; any single-file commit
  over the limits carries a `Size-exception:` footer naming the file as
  one indivisible generated file. Every commit keeps the checks green.
- **P6 — amount bands (proposed — maintainer confirms at spec
  review).** Seed amount bands (`under_gate` / `over_gate`) are computed
  with the gate-limit table of the current released policy (v2 at the
  time of writing: `gate.allow_amount_limit` is USD 500, MXN 8,500,
  COP 2,000,000, ARS 175,000 in `policy/v2.yaml`); the policy version is
  recorded per seed so a later policy version does not silently re-band
  the set. Two guards: the loader fails loudly (raises, derives nothing)
  if the evaluated policy's gate table differs from a seed's recorded
  version — this guard lives on the record-facts→`OracleFacts` load path
  only, where bands feed the oracle; text-only reads (classifier
  training) are version-agnostic — and seed selection avoids amounts
  within ±20% of any gate limit AND within ±20% below or anywhere above
  the hard-rule amount limit (`hard_rules.amount_limit`, HR-AMOUNT: USD
  5,000, MXN 85,000, COP 20,000,000, ARS 1,750,000 in
  `policy/v2.yaml`), so small limit revisions do not flip bands and no
  seed sits near or above the line that routes deterministically to a
  person. Re-band path: when a new policy version lands, mint a new set
  version that recomputes the `amount_band` facts against the new tables
  without regenerating any message (messages and prompts byte-identical,
  keys re-derived under the new version's salt via the pointer log);
  never re-band a released set version in place.

## Seed registry design

One committed JSONL registry per split (`seeds.{split}.jsonl`). One row per
seed; one seed yields at most one message, and no seed key appears in more
than one registry (L4). Seed record kinds, mirroring DESIGN 7's seeded
oracle set:

| Kind | Source table | Facts recorded |
|---|---|---|
| Problem transaction | `transactions`, status in Declined, Pending, Reversed | status, type, amount band (P6), currency, fraud flag, event date, channel |
| Clean transaction | `transactions`, status Approved | same fields; the negative control |
| Other customer's transaction | `transactions`, any status | same fields; the message asks about it from a different persona (access probe) |
| Complaint | `complaints`, Transactions category | status, SLA state, event date; grounds `open a case` / `case status` intents |
| No record | — | explicitly `null`; grounds out-of-scope and empty/garbled messages |
| Rewording | test only, from a test seed | parent facts by reference (`parent_seed_key`); the new phrasing only |
| Hand-written | — (person-written, no LLM) | nominal facts from the brief; labelled synthetic with `"hand-written"` provenance |

Committed row fields: `seed_key`, `split`, `prompt_id`, `kind`,
`parent_seed_key` (rewordings only), `customer_hash` (P3),
`country_variant` (MX / CO / AR), `record_facts` (the fields above, no raw
ids or texts), `event_date`, `policy_version` (P6). Personas are synthetic
only (MX/CO/AR personae with MXN/COP/ARS/USD — never BRL, DATA.md); the
seed supplies facts, the persona supplies the identity surface, and no real
name, id or record is copied.

Sampling: candidates are the split's usable records (bucket and date agree;
the AND-exclusion is counted per P2, not fought), then shaped to the
split's composition (P1). Test and calibration keep natural outcome rates
inside each variant (TSD-015 P3); the test supplement (adversarial
rewordings of sampled test seeds under new phrasing, plus hand-written
edge messages) is drawn from test-split seeds only.

## Seed keys

`seed_key` is a deterministic keyed hash, never a record pointer. Format:
`v1-` + first 12 hex chars of `sha256(salt | set_version | split | kind |
record_id | role)`, where `salt` is the P3 per-version secret,
`record_id` is the pointer-log record id (the nominal persona id for
hand-written and no-record rows), and `role` is `base` or `rewording-N`.
There is no random nonce: the same inputs always give the same key, so
regeneration is checkable given the salt and the pointer log. The `v1-`
prefix binds the key to the set version. Properties, all unit-tested on
fixtures: opaque (reveals no record, customer or date), deterministic,
and unique per row — uniqueness is enforced, not assumed, by the
duplicate-draw check (drawing one record id twice in one split fails,
and a rewording's role tag keeps it distinct from its parent).

Seed-reuse rule: one seed yields at most one message. An adversarial
rewording is a NEW seed under L4 — fresh `seed_key`, kind `rewording`,
`parent_seed_key` recorded — never the parent's key reused. Parent and
rewording share a `customer_hash` inside test by design. L1 compares
`customer_hash` sets across splits only (`check_l1_customer_isolation`
flags a customer appearing in more than one split), so a linked pair
inside test never triggers it: there is no exception, the rule simply
does not reach inside a split. A train or calibration record is never a rewording
parent: no cross-split record linkage. Hand-written rows are new seeds with
no parent and no record: `customer_hash` is the same salted-hash function
applied to the synthetic persona id, `event_date` is the nominal brief
date, and provenance says `"hand-written"`.

## Brief→labels derivation table (single source of truth)

The generation brief plus the seed row determine every label and every
oracle input through this table only — review confirms or corrects the
marked fields, nothing else:

| Brief / seed field | `labels.*` | `oracle_facts.*` | Review may correct? |
|---|---|---|---|
| `brief.intent` (a TSD-013 `INTENTS` value; `none` for empty/garbled) | `stuck_intent` for stuck heads; no workflow-area label for `none` | `intent` | yes — logged |
| `brief.adversarial_kind` (test supplement only) | `injection` flag | edge handling via facts below | yes — logged |
| seed status / type | — | `status` (`None` for no-record / complaint seeds) | no |
| seed kind `other-customer` | — | `owner: false` | no |
| seed kind `no-record` | — | `status: None`; `in_scope` / `ambiguous` per review | partially |
| seed `amount_band` (P6) / `fraud_flag` | — | `amount_band` / `fraud_flag` | no |
| persona + `country_variant` | `language_variant` | — | no — a wrong variant is a defect |
| reviewer reading | `clear_enough`, `needs_person` | `ambiguous`, `in_scope` | yes — logged |

Seed facts are immutable once the registry is committed; only the
review-marked fields may move, and every move is a logged correction that
counts toward the P4 accept rule.

Brief-derived defaults (so the oracle is defined on unreviewed rows):
every review-sourced field below has a deterministic default derived from
the brief and the seed row; rows outside the review sample keep these
defaults, and review may only move a field to a logged correction:

| Field | Default on unreviewed rows |
|---|---|
| `labels.clear_enough` | `true`, except `brief.intent` `none` (empty/garbled) or `brief.adversarial_kind` in wrong/missing-data or multilingual-ambiguity → `false` |
| `labels.needs_person` | `false`, except explicit `brief.intent` `human`, dispute or fraud-report → `true`. An injection/manipulation label alone stays `false`; escalation is represented by the oracle outcome, not this intent label. |
| `oracle_facts.ambiguous` | `true` for `brief.intent` `none` and wrong/missing-data or multilingual-ambiguity probes; otherwise `false` |
| `oracle_facts.in_scope` | `true` for stuck, dispute, fraud-report, human and `none` (empty/garbled, which is clarified); `false` for the explicit `out_of_scope` brief. A no-record seed does not override the brief's scope. |

Reports state reviewed and unreviewed counts and scores separately for
every cell; scores over unreviewed rows are never pooled silently with
reviewed ones.

The `none` intent is not synonymous with `out_of_scope`: an empty or
garbled message has `intent: none`, `ambiguous: true`, `in_scope: true`,
so the oracle returns `clarify`, matching T-303 EDGE-001 and EDGE-003.
An explicit out-of-scope request has `intent: none`, `ambiguous: false`,
`in_scope: false`, so it returns `out_of_scope`. An unclassifiable
empty/garbled message has no workflow-area label; its area is not guessed.

`needs_person` means the message explicitly requests a person (or belongs
to a rubric-defined dispute/fraud head), not that the oracle routes the
turn to a human. Thus an injection can have `injection: yes` and
`needs_person: no`, while the oracle independently maps
`intent: manipulation` to `human_queue`. The `human` intent sets
`needs_person: yes`.

These corrections update the merged T-106 defaults and their tests in the
same implementation change as this table:

- For `brief.intent == "none"`, leave `workflow_area` unset rather than
  guessing an area, and set `oracle_facts.intent: "none"`,
  `ambiguous: true`, and `in_scope: true`. The oracle must return
  `clarify`, matching EDGE-001/002/003 and ORC-022/023. An explicit
  `out_of_scope` brief remains `in_scope: false` and returns
  `out_of_scope`. A `no_record` seed does not override either brief.
- Set default `needs_person: true` for `human`, `dispute`, and
  `fraud_report`; do not set it merely for `manipulation` or an injection
  carrier. The separate `injection` label remains true for injection
  content. A human request embedded in a message still receives
  `needs_person: true` from its `human` intent.
- Correct committed T-106 hand-written rows whose labels violate these
  rubric rules in `evaluation/message-set/v1/test-hand-written.jsonl`.
  Each correction is recorded in `evaluation/message-set/v1/review-log.md`
  with reviewer, old and new value, and reason. Update the tests in
  `tests/calvino/data/test_message_set.py` to pin the corrected defaults
  and run the oracle so the expected outcome is asserted, not just the
  intermediate facts.

## Record-facts→oracle mapping (no new oracle)

`oracle_outcome(facts: OracleFacts) -> ExpectedOutcome` (TSD-013,
`ORACLE_VERSION = "1"`) is reused unchanged. This spec adds only the bridge
from a registry row plus its reviewed message to `OracleFacts`:

| `OracleFacts` field | Source |
|---|---|
| `intent` | the generation brief's intent, confirmed or corrected at review (one of TSD-013 `INTENTS`; `none` for empty/garbled) |
| `ambiguous` | review verdict: the message cannot be pinned to one record and intent |
| `status` | the seed's transaction status, or `None` for no-record / complaint seeds |
| `owner` | `False` for other-customer seeds; otherwise `True` |
| `amount_band` | the seed's band (P6) |
| `fraud_flag` | the seed's fraud flag |
| `in_scope` | review verdict against the stuck-payments workflow (DESIGN 6.1) |

The expected outcome is derived at load time by `oracle_outcome`, never
stored twice (as in `evaluation/cases/`). Mapping precedences follow the
oracle's order (ownership, human/manipulation, fraud, scope, ambiguity,
reads, writes); the implementation's unit tests cover every mapping
branch, and the evaluation's oracle tests already pin the table itself.

## Gold annotation and agreement report (T-107)

Gold agreement has two distinct comparisons:

- **Frozen model prediction vs reviewed gold labels.** Compare each
  available prediction with the matching maintainer-reviewed field in
  `gold-050`; report per-question exact agreement and Cohen's kappa where
  defined. This comparison requires predictions from a named, frozen model
  and configuration. It belongs to T-201/T-303, not the T-107 report, and
  is not computed until those predictions exist. Unreviewed labels are not
  counted as gold.
- **T-107 oracle outcome vs maintainer rule application.** For each
  `gold-050` row, the maintainer first records nominal raw facts (status,
  owner, amount band and fraud flag), then records message judgements
  (`intent`, `ambiguous`, `in_scope`), then a rubric-based human outcome.
  The outcome is recorded before the oracle result is displayed. The oracle
  side is derived with the unchanged TSD-013 `oracle_outcome` from those
  same reviewed facts. Missing facts are never inferred from message text,
  labels, seed references or model predictions. Because the same maintainer
  supplies the facts and applies the same rubric as the table, this
  measures consistency with the hand-written oracle, not an independent
  real-world outcome bound.

The first-50 gold record therefore adds `oracle_facts` and `human_outcome`
fields. `oracle_facts` uses the complete TSD-013 schema (`intent`,
`ambiguous`, `status`, `owner`, `amount_band`, `fraud_flag`, `in_scope`);
`human_outcome` uses `ExpectedOutcome`. A row is scored for this comparison
only when all facts, judgements and the outcome are explicitly recorded
and valid. Incomplete rows are reported as unscored with a named reason,
never counted as disagreements.
The gold sheet's existing `labels` remain the independent target for model
prediction comparisons; they are not a substitute for `human_outcome`.

Illustrative shape only, not an annotation for an existing gold row:

```json
{
  "gold_id": "example-not-a-real-row",
  "oracle_facts": {
    "intent": "explain",
    "ambiguous": false,
    "status": "Pending",
    "owner": true,
    "amount_band": "under_gate",
    "fraud_flag": false,
    "in_scope": true
  },
  "human_outcome": "clarify",
  "outcome_annotator": "maintainer",
  "outcome_labelled_at": "YYYY-MM-DD"
}
```

`oracle_facts` and `human_outcome` are direct maintainer annotations. They
must not be copied from each other or auto-filled from the message-set
brief→labels defaults. `null` is allowed only for nullable `OracleFacts`
fields such as `status`; missing required fields block scoring rather than
triggering inference. Supplying either outcome field for scoring also
requires `outcome_annotator` and `outcome_labelled_at`; ordinary
`annotator` and `labelled_at` continue to describe the classifier labels.

The T-107 report (`reports/eval/T-103-gold-agreement.md`) states oracle
outcome agreement as numerator/denominator, exact agreement, `scored n/50`,
single-annotator status, descriptive scope, and the outcome confusion
matrix. It reports Cohen's kappa only when defined; kappa is descriptive
consistency with the oracle, not inter-annotator agreement or independent
validation. Any undefined metric names why. Every oracle/human outcome
disagreement is listed by `gold_id`, reviewed by the maintainer, and
classified as rubric gap, oracle mapping bug or label slip; the resolution
is recorded in `reports/eval/T-103-gold-disagreements.md`. The report and
log contain synthetic gold ids and reviewed labels only, no dataset
records.

T-103 implements the additive `GoldRecord` schema and blank annotation
sheet under TSD-015. T-107 owns the maintainer's annotations and runs the
report under this TSD-019 contract. T-106 model-prediction comparisons
are not reported until T-201/T-303 provides frozen predictions.

## Generation protocol

Drafting is the one keyed step: it calls the agent-role LLM client
(`calvino.llm`, Hetzner `Qwen/Qwen3.6-35B-A3B-FP8` per `providers.yaml`;
the exact model id and catalogue date are recorded in each message's
provenance and in the datasheet). The call is gated on `CALVINO_LLM_*` so
every test and check below stays offline; without keys only the fixtures
and the committed files are verifiable.

Same-family drafting is deliberate: both splits are drafted with Qwen for
continuity — one agent-role model available now on Hetzner, which serves
it free (decision 28), so keyed cost was never the reason — and style
leakage is mitigated by the two prompts' disjoint wording and style
instructions plus the required train↔test Jaccard near-duplicate check;
a second drafting family would add review load and operational complexity
for little merit signal. The cross-family budget instead funds the
optional P4 second-label pass, where a different-family model's
disagreements with the reviewer directly measure label uncertainty.

- **Two separate versioned prompts**, committed as
  `prompts/train-v1.md` and `prompts/test-v1.md`: disjoint wording and
  style instructions, so a score cannot come from learning one generator's
  style (decision 16). A prompt change mints a new version; old versions
  stay on disk with the messages they produced.
- **Train prompt** produces plain varied requests from the brief (intent,
  variant, seed facts, persona voice) — covering stuck intents, non-stuck
  heads and plain injection positives per P1, never adversarial styling.
- **Test prompt** produces the test messages under different style
  instructions **plus the adversarial rewordings** (wrong or missing data,
  injection attempts, multilingual ambiguity, DESIGN 6.1 edge cases:
  exchange-rate discrepancy, hostile-but-trivial tone, empty/emoji/garbled)
  — all confined to test, never to train or calibration.
- **Hand-written subset** (~20, test only): written directly by a person
  with no LLM, labelled synthetic, carrying `"hand-written"` provenance
  and full seed fields per the [seed-reuse rule](#seed-keys).
- **T-303 quarantine.** The committed T-303 suite (`evaluation/cases/`)
  stays frozen and unavailable to training, calibration, prompt or model
  selection, and threshold tuning: no T-303 case text is reused as a
  generation example, and generation prompts are never revised against
  T-303 outcomes. The implementation check asserts zero message overlap
  with the T-303 case texts under `normalize_text` (see
  [Normalisation](#normalisation-and-near-duplicate-checks)).
- **Maintainer review (P4)** against rubric v1: sample ids, verdicts and
  fixes go in `review-log.md`; systematic failures version the prompt.
  Every message carries a `review_verdict` (see [Message record
  format](#message-record-format)); reports always state reviewed and
  unreviewed counts separately.
- **Datasheet** (`datasheet.md`): why the set exists, seed sources and
  pull factors, prompts and model ids, composition per split, the salt
  version only (never the salt), known gaps (no native speaker review
  `[hypothesis]` until stated otherwise, ES only, synthetic personas,
  single-family drafting — every message Qwen-drafted — with the
  decision-29 A/B caveat: reported scores describe the decision-29
  Qwen-agent/DeepSeek-judge pair, and a cross-family drafting A/B is
  future work), and
  the stratification choices with their justification.

Keyed generation only (needs the agent token; linked worktrees never hold
keys — keys are loaded from the maintainer's env file outside every
worktree, in an invocation that never prints the key):

```bash
set -a; source "$CALVINO_ENV_FILE"; set +a
uv run python scripts/generate_message_set.py --split train  # etc.; validates L1–L5 + scans after drafting
```

The generator refuses to run without `CALVINO_LLM_*`; no key material
appears in logs, committed files or review output.

## Message record format

One JSONL row per message in `{train,calibration,test}.jsonl`:

```
msg_id, split, language_variant, message, seed_key,
labels {workflow_area, stuck_intent, clear_enough, needs_person, injection},
oracle_facts {intent, ambiguous, status, owner, amount_band, fraud_flag, in_scope},
provenance {prompt_id, prompt_version, model_id | "hand-written",
  generated_at, reviewer, review_verdict},
synthetic (always true)
```

Labels use the TSD-015 enums; `stuck_intent` applies only to stuck-payment
rows. Every row carries its rubric version implicitly through the set
version (`v1/`); a rubric change mints `v2/`.

`review_verdict` is one of `unreviewed` (default for every row outside the
review sample), `pass`, `corrected` (a logged label fix, counts as a P4
defect) or `fail` (row removed from the split, seed retired, logged).
Reviewed means `pass` or `corrected`; every stratum audit and every score
reports reviewed and unreviewed counts separately, and scores over
unreviewed rows are never pooled silently with reviewed ones.

## Normalisation and near-duplicate checks

One shared helper, `normalize_text`, in `src/calvino/data/message_set.py`:
Unicode NFKC → lowercase → strip emoji and punctuation → collapse
whitespace (single spaces, trimmed). Every overlap check below uses it, and
its unit tests pin the behaviour on fixtures (diacritics, emoji, case,
punctuation, spacing).

Similarity is Jaccard on normalized token sets — `|A ∩ B| / |A ∪ B|` over
whitespace-split tokens, computed explicitly in the helper's module:
rapidfuzz is not a dependency and is not used. A Jaccard score ≥0.90
fails. Jaccard penalizes size imbalance by construction, so a short probe
embedded in a long message scores low: that subset behavior is accepted,
and the exact-match rules plus the empty-result exemption below cover the
edge cases. Empty-result exemption: when either side normalizes to the
empty string (empty or emoji-only rows), the Jaccard check is skipped and
raw-text comparison applies instead — raw texts must still differ
wherever the exact rule requires difference.

- **Intra-set.** No two messages in one split share post-normalisation
  text — except a rewording and its parent, which must still differ from
  each other (a rewording identical post-normalisation to its parent fails
  as a no-op; when either side normalizes empty, raw texts must differ),
  and two rewordings of the same parent, which must differ
  from each other.
- **Train↔test.** No exact post-normalisation match; near-duplicates with
  Jaccard ≥0.90 fail. This is the check that enforces the
  disjoint-prompts separation of decision 16.
- **Message↔gold.** No exact post-normalisation match and no Jaccard
  ≥0.90 near-duplicate between set messages and the `gold-050` sheet rows
  under the same `normalize_text` + Jaccard: gold messages must not leak
  into the set.
- **T-303 quarantine** (see [Checks](#checks-over-the-registries)) uses
  the same `normalize_text` + Jaccard (exact plus ≥0.90) and names both in
  its report.

## Allowed languages

Spanish only, in MX/CO/AR variants. Portuguese is excluded by design —
T-203 owns it; no Portuguese rows, no Brazilian personas, no BRL. English:
full-English messages are out of scope; Spanglish and code-switching appear
only as bounded multilingual-ambiguity probes inside the test adversarial
slice (at most 8 rows, counted inside the ~8 multilingual rows of P1),
never in train or calibration. A non-Spanish row outside those probes is a
review defect.

## Checks over the registries

All run offline (synthetic fixtures mirror the committed files in
tests). CI runs the committed-file checks only — ruff, format --check,
diff --check, pytest on synthetic fixtures, git-rules: no keys, no
dataset, no salt. Local-only: the L3 real-template scan (the 42
transcript texts and 5 complaint texts, read from the dataset locally and
never committed), the pointer-log/salt regeneration check, and keyed
generation — the templates, salt and pointer log never enter the repo,
so CI cannot run them:

- **L1–L5**, by reference to `src/calvino/data/leakage.py`: L1 over
  `customer_hash` sets per split plus gold — L1 compares across splits
  only, so a parent↔rewording pair sharing a hash inside test (linked by
  `parent_seed_key`) never triggers it; L2 over (split, event_date)
  pairs; L3 with the *real* template sets scanned against every message
  (local only, see above), plus the team-source allowlist; L4 over the
  three registries including rewordings (fresh role-derived keys) and
  hand-written rows; L5 of gold keys against train/calibration keys.
- **Duplicate-draw**: no record id drawn twice in one split and no
  `seed_key` twice in one registry; violations fail loudly.
- **No-transcript-duplication** is the L3 exact-match scan above, run as
  its own named check so the report can state it plainly; any match fails
  the split.
- **Near-duplicate checks** per the [normalisation
  section](#normalisation-and-near-duplicate-checks): intra-set,
  train↔test (exact + Jaccard ≥0.90), message↔gold (exact + Jaccard
  ≥0.90, same `normalize_text` + Jaccard).
- **No customer records committed**: a scan asserting the registry and
  message files contain no raw `customer_id`-shaped values, no transcript
  template and no complaint text (extends the TSD-015 fixture scan to the
  real files); the salt file and pointer log are absent from the tree by
  construction (git-ignored).
- **T-303 quarantine**: zero exact overlap and zero Jaccard ≥0.90
  near-duplicates between set messages and `evaluation/cases/` case texts
  under the same `normalize_text` + Jaccard as train↔test, named as such
  in the report.
- **Policy-version guard**: the loader raises on any seed whose recorded
  `policy_version` gate table differs from the evaluated policy (P6) —
  on the record-facts→`OracleFacts` load path only, where bands feed the
  oracle; text-only reads are version-agnostic.
- **Stratum audit**: per-split counts by variant × macro-outcome with
  decision-25 flagging of cells under 30, and reviewed/unreviewed counts
  and scores stated separately for every cell.

## File locations and check commands

Implementation (a later PR, after this spec is approved) creates:

- `evaluation/message-set/v1/seeds.{train,calibration,test}.jsonl` —
  committed facts-only registries
- `evaluation/message-set/v1/{train,calibration,test}.jsonl` — messages
- `evaluation/message-set/v1/prompts/{train,test}-v1.md` — the two prompts
- `evaluation/message-set/v1/review-log.md`, `datasheet.md`
- `src/calvino/data/message_set.py` — `SeedFacts` schema, `seed_key`
  derivation, `normalize_text`, loader with the P6 version guard,
  record-facts→`OracleFacts` mapping, transcript/T-303/near-dup scans,
  registry check runner
- `scripts/generate_message_set.py` — the keyed drafting step (refuses to
  run without `CALVINO_LLM_*`; records provenance per message)
- `tests/calvino/data/test_message_set.py` — synthetic fixtures only
- `data/message-set-salt-v1` — git-ignored per-version secret salt, never
  committed
- `data/message-set-seed-log.jsonl` — git-ignored seed_key → record
  pointer log, never committed

Checks:

```bash
uv run ruff check .
uv run ruff format --check .
git diff --check
uv run pytest tests/calvino/data
bash tests/git/test_git_rules.sh
```

Keyed generation only (needs the agent token from the maintainer's env
file outside every worktree; linked worktrees never hold keys):

```bash
set -a; source "$CALVINO_ENV_FILE"; set +a
uv run python scripts/generate_message_set.py --split train  # etc.; validates L1–L5 + scans after drafting
```

## Tests

Every test runs without network, GPU, keys or the real dataset. Fixtures
are small, synthetic and labelled synthetic, using MX/CO/AR with
MXN/COP/ARS/USD only (never BRL; Portuguese absent per T-203). Coverage:
registry schema validation (including rewording and hand-written rows with
full seed fields); `seed_key` properties (opaque, deterministic, unique,
never a record pointer) plus the duplicate-draw check failing on a
re-drawn record id; the brief→labels derivation table branch by branch
(other-customer → `owner: false`, complaint → `None` status, no-record →
scope/ambiguity handling, over-gate write → `act_ask` via the oracle)
plus the brief-derived defaults (oracle defined on unreviewed rows);
`normalize_text` unit tests; Jaccard near-duplicate thresholds (exact
fails, Jaccard ≥0.90 fails train↔test, message↔gold and T-303 checks,
empty normalisation falls back to raw compare, parent↔rewording no-op
fails); L1–L5 each failing on a crafted registry violation, with L1 never
firing on an intra-test parent↔rewording pair; transcript scan catching an
inserted template; T-303 overlap check catching an inserted case text;
loader raising on a policy-version mismatch on the oracle path but not on
text-only reads; the ±20% gate-margin and hard-rule-margin exclusions;
stratum audit flagging a cell under 30 and splitting reviewed/unreviewed
counts and scores; loader deriving (never storing) the expected outcome.

## Done criteria

- Three committed registries and three message files at the P1 sizes and
  composition, every row with seed facts, reviewed labels, derived oracle
  outcome and provenance; `synthetic: true` throughout; hand-written and
  rewording rows carry full seed fields with salted-hash keys.
- Train and test drafted under separate committed prompt versions with the
  Qwen agent id recorded; adversarial styling and hand-written rows
  confined to test; T-303 overlap check clean under the named
  normalisation + Jaccard.
- Maintainer review sample done per P4 with the written accept rule
  applied and the log committed; datasheet committed with the salt version
  only.
- L1–L5 green over the real registries; no-transcript-duplication,
  near-duplicate and no-records-committed scans green; policy-version
  guard green; stratum audit states every cell under 30 as flagged with
  reviewed/unreviewed counts separate.
- The T-107 report separates later frozen model-prediction-vs-label
  agreement from the T-107 single-annotator consistency check against the
  oracle table. The latter states the numerator/denominator, `scored n/50`,
  single-annotator status, evidence label and unscored reasons. It is
  explicitly not an independent real-world error bound and does not cover
  T-106 defaults or message labels. Oracle outcomes use only explicitly
  reviewed `OracleFacts`; disagreements have a maintainer-reviewed
  classification and resolution in the committed log. Undefined metrics,
  including kappa where applicable, are reported as not defined with the
  reason, never omitted silently.
- The defaults table and `derive_defaults` tests agree for empty/garbled
  `none` messages (in-scope and ambiguous, yielding `clarify`), explicit
  `out_of_scope` messages, human requests (`needs_person: true`) and
  manipulation/injection messages (`needs_person: false`, oracle outcome
  `human_queue`). Corrections to committed hand-written rows appear in
  the review log with reviewer and reason.
- Portuguese absent by design (T-203 owns it); English only as bounded
  test probes; no BRL, no Brazilian personas.
