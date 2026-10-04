# TSD-018: Team-generated customer message set (T-106)

| | |
|---|---|
| Status | proposed — maintainer confirms at spec review |
| Branch | `feat/message-set` (the T-106 card says `data/message-set`; that type is rejected by the push hook, so `feat/` stands) |
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
record-facts→oracle mapping, the two generation prompts, the message files,
the review log and the datasheet. Boundary with TSD-013: the outcome oracle
(`oracle_outcome` in `calvino.evaluation`) already exists and is reused as
is; this spec creates **no competing oracle**, per the T-106 card. Boundary
with T-203: Portuguese is explicitly out of this spec; the set is Spanish
only (MX, CO, AR variants).

## Proposed defaults

Every item below resolves one open choice. Each is marked **proposed —
maintainer confirms at spec review**, and the implementation PR changes
nothing marked this way without a new entry here.

- **P1 — sizes (proposed — maintainer confirms at spec review).** Train 600,
  calibration 240, test 300 (total 1,140), composed as follows. Train is
  stratified over 6 stuck intents × 3 country variants (18 cells, ~33 per
  cell); resampling is allowed on train only and is documented in the
  datasheet, never silent (TSD-015 P3). Calibration is even across variants
  (3 × 80) with a natural outcome mix inside each variant, so per-variant
  calibration reads stay at or above decision 25's 30-case line. Test is
  240 seed-generated (even variants, natural mix) plus a 60-case supplement
  confined to test: ~40 adversarial rewordings and ~20 hand-written
  messages. The supplement is reported as its own slice; any reported slice
  under 30 cases is flagged, not failed (decision 25).
- **P2 — seed pull factor (proposed — maintainer confirms at spec
  review).** A candidate record is usable only when its customer bucket
  *and* its event date agree on one split (TSD-015 AND-condition). Under
  near-uniform volume the usable share is roughly
  0.70×0.67 + 0.15×0.19 + 0.15×0.17 ≈ 0.52 `[hypothesis]`, so the exclusion
  rate is ~50% and the implementation pulls about twice as many candidate
  seeds as messages needed per split; the split report states the achieved
  exclusion counts.
- **P3 — committable registries (proposed — maintainer confirms at spec
  review).** Committed registries carry seed *facts*, never records: no real
  `customer_id`, no transcript text, no complaint text (DATA.md: committed
  outputs are aggregates only, never records). Customer identity is stored
  as a truncated salted hash (`sha256(customer_id + salt)[:16]`, salt
  committed in the datasheet) — enough for the L1 equality check, not
  enough to identify anyone. The full seed_key → record pointer log lives
  in the git-ignored `data/` folder for regeneration and is never
  committed.
- **P4 — review sample (proposed — maintainer confirms at spec
  review).** The maintainer reviews a random sample of ≥50 messages per
  split against rubric v1 before the split is used. A systematic failure
  mints a new prompt version; reviewed messages are never silently edited
  into passing.
- **P5 — file home (proposed — maintainer confirms at spec review).**
  Versioned files under `evaluation/message-set/v1/` (see [File
  locations](#file-locations-and-check-commands)); code in
  `src/calvino/data/message_set.py` with tests in
  `tests/calvino/data/test_message_set.py`.
- **P6 — amount bands (proposed — maintainer confirms at spec review).**
  Seed amount bands (`under_gate` / `over_gate`) are computed with the
  gate-limit table of the current released policy (`policy/v2.yaml`);
  the policy version is recorded per seed so a later policy version does
  not silently re-band the set.

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

Committed row fields: `seed_key`, `split`, `prompt_id`, `kind`,
`customer_hash` (P3), `country_variant` (MX / CO / AR),
`record_facts` (the fields above, no raw ids or texts), `event_date`,
`policy_version` (P6). Personas are synthetic only (MX/CO/AR personae with
MXN/COP/ARS/USD — never BRL, DATA.md); the seed supplies facts, the
persona supplies the identity surface, and no real name, id or record is
copied.

Sampling: candidates are drawn from the split's usable records (bucket and
date agree; the ~50% AND-exclusion of P2 is counted, not fought), then
shaped to the split's composition (P1). Test and calibration keep natural
outcome rates inside each variant (TSD-015 P3); the test supplement
(adversarial rewordings of sampled seeds under new phrasing, plus
hand-written edge messages) is drawn from test-split seeds only.

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

Oracle-vs-gold agreement is measured on reviewed gold labels, not inferred
from synthetic generation: per-question exact agreement plus Cohen's kappa
on needs-a-person and on oracle outcome vs gold outcome, with n stated
(TSD-015; the sheet holds 50 rows, 18 labelled at the time of writing, so
early reports name their n). Disagreements are read and logged as rubric
gap, mapping bug or label slip.

## Generation protocol

Drafting is the one keyed step: it calls the agent-role LLM client
(`calvino.llm`, Hetzner `Qwen/Qwen3.6-35B-A3B-FP8` per `providers.yaml`;
the exact model id and catalogue date are recorded in each message's
provenance and in the datasheet). The call is gated on `CALVINO_LLM_*` so
every test and check below stays offline; without keys only the fixtures
and the committed files are verifiable.

- **Two separate versioned prompts**, committed as
  `prompts/train-v1.md` and `prompts/test-v1.md`: disjoint wording and
  style instructions, so a score cannot come from learning one generator's
  style (decision 16). A prompt change mints a new version; old versions
  stay on disk with the messages they produced.
- **Train prompt** produces plain varied requests from the brief (intent,
  variant, seed facts, persona voice).
- **Test prompt** produces the test messages under different style
  instructions **plus the adversarial rewordings** (wrong or missing data,
  injection attempts, multilingual ambiguity, DESIGN 6.1 edge cases:
  exchange-rate discrepancy, hostile-but-trivial tone, empty/emoji/garbled)
  — all confined to test, never to train or calibration.
- **Hand-written subset** (~20, test only): written directly by a person
  with no LLM, labelled synthetic, carrying `"hand-written"` provenance.
- **T-303 quarantine.** The committed T-303 suite (`evaluation/cases/`)
  stays frozen and unavailable to training, calibration, prompt or model
  selection, and threshold tuning: no T-303 case text is reused as a
  generation example, and generation prompts are never revised against
  T-303 outcomes. The implementation check asserts zero message overlap
  with the T-303 case texts.
- **Maintainer review (P4)** against rubric v1: sample ids, verdicts and
  fixes go in `review-log.md`; systematic failures version the prompt.
- **Datasheet** (`datasheet.md`): why the set exists, seed sources and
  pull factors, prompts and model ids, composition per split, known gaps
  (no native speaker review `[hypothesis]` until stated otherwise, ES only,
  synthetic personas), and the stratification choices with their
  justification.

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

## Checks over the registries

All run offline on the committed files (synthetic fixtures mirror them in
tests):

- **L1–L5**, by reference to `src/calvino/data/leakage.py`: L1 over
  `customer_hash` sets per split plus gold; L2 over
  (split, event_date) pairs; L3 with the *real* template sets (the 42
  transcript texts and 5 complaint texts — the implementation reads them
  from the dataset locally and never commits them) scanned against every
  message, plus the team-source allowlist; L4 over the three registries
  including the test supplement and hand-written rows; L5 of gold keys
  against train/calibration keys.
- **No-transcript-duplication** is the L3 exact-match scan above, run as
  its own named check so the report can state it plainly; any match fails
  the split.
- **No customer records committed**: a scan asserting the registry and
  message files contain no raw `customer_id`-shaped values, no transcript
  template and no complaint text (extends the TSD-015 fixture scan to the
  real files).
- **T-303 quarantine**: zero text overlap between set messages and
  `evaluation/cases/` case texts.
- **Stratum audit**: per-split counts by variant × macro-outcome with
  decision-25 flagging of cells under 30.

## File locations and check commands

Implementation (a later PR, after this spec is approved) creates:

- `evaluation/message-set/v1/seeds.{train,calibration,test}.jsonl` —
  committed facts-only registries
- `evaluation/message-set/v1/{train,calibration,test}.jsonl` — messages
- `evaluation/message-set/v1/prompts/{train,test}-v1.md` — the two prompts
- `evaluation/message-set/v1/review-log.md`, `datasheet.md`
- `src/calvino/data/message_set.py` — `SeedFacts` schema, loader,
  record-facts→`OracleFacts` mapping, transcript/T-303 scans, registry
  check runner
- `scripts/generate_message_set.py` — the keyed drafting step (refuses to
  run without `CALVINO_LLM_*`; records provenance per message)
- `tests/calvino/data/test_message_set.py` — synthetic fixtures only
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

Keyed generation only (needs the agent token from `main/.env`; linked
worktrees never hold keys):

```bash
uv run python scripts/generate_message_set.py --split train  # etc.; validates L1–L5 + scans after drafting
```

## Tests

Every test runs without network, GPU, keys or the real dataset. Fixtures
are small, synthetic and labelled synthetic, using MX/CO/AR with
MXN/COP/ARS/USD only (never BRL). Coverage: registry schema validation;
mapping branches (other-customer → `owner: false`, complaint → `None`
status, no-record → scope/ambiguity handling, over-gate write → `act_ask`
via the oracle); L1–L5 each failing on a crafted registry violation;
transcript scan catching an inserted template; T-303 overlap check
catching an inserted case text; stratum audit flagging a cell under 30;
loader deriving (never storing) the expected outcome.

## Done criteria

- Three committed registries and three message files at the P1 sizes,
  every row with seed facts, reviewed labels, derived oracle outcome and
  provenance; `synthetic: true` throughout.
- Train and test drafted under separate committed prompt versions; model
  id recorded; adversarial rewordings and hand-written rows confined to
  test; T-303 overlap check clean.
- Maintainer review sample done per P4 with the log committed; datasheet
  committed.
- L1–L5 green over the real registries; no-transcript-duplication and
  no-records-committed scans green; stratum audit states every cell under
  30 as flagged.
- Oracle-vs-gold agreement reported on reviewed labels with n stated.
- Portuguese absent by design (T-203 owns it); no BRL, no Brazilian
  personas.
