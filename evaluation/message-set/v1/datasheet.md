# Datasheet — message set v1 (TSD-019, T-106)

## Why this set exists

The dataset's transcripts are templated and carry no label information
(decision 16), so there is no customer text to calibrate or fine-tune
the classifiers on. The dataset supplies structured seed facts and the
human baseline; every message in this set is team-generated and labelled
synthetic. The classifiers' scores are the policy's main input, so the
text they train on must be disjoint across splits and free of dataset
template wording.

## Seed sources and pull factors

Candidate seeds are usable records only: the customer bucket and the
event date agree on one split (TSD-015 AND-condition), then sampling
shapes each split to the P1 composition. There is no fixed oversample
factor; the split report states considered, usable, drawn and excluded
counts per split at generation time.

Stratified draw (pending live re-pull — the committed registries below
are still the pre-remediation unstratified pull and will be replaced):
per-kind quotas implement the P1 composition — train 450
stuck-grounding problem transactions plus 60 complaint heads plus 60
clean carriers (570 drawn) with 30 nominal no-record rows appended;
calibration and test 180 plus 24 plus 30 (234 drawn) with 6 nominal
no-record rows appended — each quota cell split evenly across
MX/CO/AR. Stuck-intent seeds are Transfer/Payment problem transactions
only; every quota cell is fail-closed (a short cell raises
SeedShortfall, never backfills), and the complaint floors are enforced
on drawn counts. Row-level hardening, all counted as explicit skipped
reasons: missing fraud/SLA flags are never coerced, record ids are
refused on duplicates, customer ids dedup first-wins (last-wins is
forbidden), and transaction type, channel and complaint status are
enum-validated. Nominal no-record rows fill only their own quota cell
and never backfill record-backed shortfalls (grow-vs-displace rule,
recorded as NO_RECORD_BACKFILLS_SHORTFALLS in code); this rule needs a
one-line TSD-019 amendment at spec review.

| Seed kind | Source table | Facts recorded |
|---|---|---|
| Problem transaction | `transactions`, status Declined / Pending / Reversed | status, type, amount band (policy v2 gate table), currency, fraud flag, event date, channel |
| Clean transaction | `transactions`, status Approved | same fields; the negative control |
| Other customer's transaction | `transactions`, any status | same fields; asked about from a different persona (access probe) |
| Complaint | `complaints`, Transactions category | status, SLA state, event date; grounds open-a-case / case-status intents |
| No record | — | explicitly `null`; grounds out-of-scope and empty/garbled messages |
| Rewording | test only, from a test seed | parent facts by reference (`parent_seed_key`); the new phrasing only |
| Hand-written | person-written, no LLM | nominal facts from the brief; `"hand-written"` provenance |

Complaint seeds ground the open-a-case / case-status intents; quotas are
never silently filled with other kinds (calibration and test pools are
thin, so the split report flags complaint-seed tightness).

Personas are synthetic only (MX/CO/AR with MXN/COP/ARS/USD — never BRL,
DATA.md). The seed supplies facts, the persona supplies the identity
surface, and no real name, id or record is copied. Portuguese is
excluded by design: T-203 owns it.

## Prompts and models

- `prompts/train-v1.md`: plain varied requests; also drafts calibration.
- `prompts/test-v1.md`: disjoint wording and style instructions, plus
  the adversarial rewordings confined to test.
- Drafting model: the agent-role LLM (`calvino.llm`, Hetzner
  `Qwen/Qwen3.6-35B-A3B-FP8` per `providers.yaml`); the exact model id
  and catalogue date are recorded in each message's provenance.
  Same-family drafting is deliberate (continuity on the one available
  agent model); the train/test Jaccard check enforces the separation,
  and the cross-family budget funds the optional second-label pass.

## Composition per split

Train 600 (450 stuck-intent: 6 intents × 3 variants × 25; 90 non-stuck
heads; 60 plain injection positives), calibration 240 (3 variants × 80
at natural outcome mix), test 300 (240 seed-generated mirroring
calibration plus a 60-case supplement: ~40 adversarial rewordings and
~20 hand-written rows). Train and calibration are drafted entirely with
the plain prompt; adversarial styling stays confined to test. Resampling
is allowed on train only and is documented here when used, never silent.

Sampler quotas behind those totals (pending live re-pull): the brief
assigns intents and injection content at generation time while kinds
ground them — Transfer/Payment problem transactions ground the six
stuck intents, complaints ground open-a-case/case-status, clean rows
carry dispute/fraud-report heads and plain injection positives, and
nominal no-record rows ground out-of-scope and empty/garbled messages.

## Salt and pointer log

Salt version `salt-v1` only — never the value. The 32-byte secret lives
in the git-ignored `data/message-set-salt-v1` (owner-only permissions);
the full seed_key → record pointer log in `data/message-set-seed-log.jsonl`
is git-ignored too. Losing either means the set cannot be regenerated.
`seed_key` is `v1-` plus 12 hex chars of the keyed hash; customer
identity is the truncated salted hash for the L1 check only.
The pointer log is written before the registries (a refused log guard
aborts the pull with nothing committed), in truncate mode at 0600 —
re-pulls replace it, never append.

## Pull evidence

Every live pull commits `pull-report.json` alongside the registries
(pending live re-pull): considered/usable/drawn/excluded/skipped
counts per split, the manifest digest, the RNG seed, the policy
version, the salt version and the gate-table hash. The committed
registries carry no raw amounts (bands only) and no gate limits (table
hash only); the checker names every vacuous check in its output, so
only exercised checks print PASS.

## Policy versioning

Seed amount bands are computed against the gate table of the released
policy recorded per seed (v2 at the time of writing). The loader raises
on the oracle path when the evaluated policy's gate table differs from
a banded seed's recorded limit; text-only reads are version-agnostic. A
new policy version mints a new set version that recomputes bands without
regenerating messages — never re-banded in place.

## Known gaps

- No native-speaker review `[hypothesis]` until stated otherwise.
- Spanish only (MX/CO/AR variants); English only as bounded Spanglish
  probes inside the test adversarial slice.
- Single-family drafting: every message Qwen-drafted. Reported scores
  describe the decision-29 Qwen-agent/DeepSeek-judge pair; a cross-family
  drafting A/B is future work.
- Scores over unreviewed rows are never pooled silently with reviewed
  ones: every report states reviewed and unreviewed counts separately.
- Residual re-identification risk `[hypothesis]`: committed rows keep
  event_date plus currency plus channel plus type, and a rare
  combination could still single out a row. Raw amounts and gate limits
  are already out; this combination stays because the oracle and the
  briefs need it.

## Implementation status

Keyless scaffolding is committed and green: `src/calvino/data/message_set.py`
(registries, derivation table, oracle bridge, normalisation, checks),
`src/calvino/data/seed_pull.py` (P2 filter-first sampler over a
lakehouse-shaped interface: usable-records filter via the AND-condition,
P6 amount margins, variant-balanced deterministic draw, complaint-seed
tightness flag, per-split considered/usable/drawn/excluded accounting),
`src/calvino/data/seed_registry.py` (facts-only writer with salted-hash
keys, git-ignored pointer log refused on committable paths, the
oracle-bridge run proving defaults fire on unreviewed rows, and the L1–L5
file entrypoint), `tests/calvino/data/test_message_set.py`,
`test_seed_pull.py`, `test_seed_registry.py` and `test_seed_runs.py`,
both prompts, the keyed `scripts/generate_message_set.py`, the offline
`scripts/check_message_registries.py`, and the 20 hand-written supplement rows
(`test-hand-written.jsonl`, merged and keyed at generation time).

Registries: format done, population blocked on the dataset env (see below).
Generation: blocked on keys.

Population procedure (documented, live run pending): the credentialed
run executes the stratified pull (fail-closed quotas, counted skips),
builds de-identified rows (bands and table hash only), appends the
nominal no-record quota cells, commits the pointer log before the
registries, and writes `pull-report.json` — then the checker runs over
the committed files with no vacuous PASS. The committed
`seeds.{train,calibration,test}.jsonl` on this branch are still the
pre-remediation pull (unstratified, raw amounts included) and will be
replaced by that run, not hand-edited.

Blocked, with owner and next step each:

- Seed-registry population (T-106, needs the dataset lakehouse via
  `CALVINO_ENV_FILE` in a credentialed shell: no dataset access from this
  environment) → full registries
  `seeds.{train,calibration,test}.jsonl` at P1 sizes. The sampler,
  writer and check entrypoint above are ready and fixture-tested; only
  the live pull and the salt creation need the credentialed run.
- Keyed drafting (T-106, needs `CALVINO_LLM_*` at generation time plus
  ~1,140 paced calls) → `{train,calibration,test}.jsonl`.
- Maintainer review sample per the accept rule (`review-log.md`) → use.
