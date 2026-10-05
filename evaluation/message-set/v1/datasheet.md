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

## Salt and pointer log

Salt version `salt-v1` only — never the value. The 32-byte secret lives
in the git-ignored `data/message-set-salt-v1` (owner-only permissions);
the full seed_key → record pointer log in `data/message-set-seed-log.jsonl`
is git-ignored too. Losing either means the set cannot be regenerated.
`seed_key` is `v1-` plus 12 hex chars of the keyed hash; customer
identity is the truncated salted hash for the L1 check only.

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

## Implementation status

Keyless scaffolding is committed and green: `src/calvino/data/message_set.py`
(registries, derivation table, oracle bridge, normalisation, checks),
`tests/calvino/data/test_message_set.py` and
`test_generate_message_set.py`, both prompts, the keyed
`scripts/generate_message_set.py`, and the 20 hand-written supplement rows
(`test-hand-written.jsonl`, merged and keyed at generation time).

Blocked, with owner and next step each:

- Seed sampling from usable records (T-106, needs the dataset lakehouse:
  no dataset access from this environment) → full registries
  `seeds.{train,calibration,test}.jsonl` at P1 sizes.
- Keyed drafting (T-106, needs `CALVINO_LLM_*` at generation time plus
  ~1,140 paced calls) → `{train,calibration,test}.jsonl`.
- Maintainer review sample per the accept rule (`review-log.md`) → use.
