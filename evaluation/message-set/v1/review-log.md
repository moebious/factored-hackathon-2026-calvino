# Review log — message set v1 (TSD-019 P4)

Weighted maintainer review against rubric v1, before any split is used.
Minimums: train ≥30 (stratified across stuck intents, non-stuck heads
and plain injection positives — never 5-per-stuck-intent only),
calibration ≥50, test ≥30 from the base slice plus all ~40 adversarial
rewordings plus all ~20 hand-written rows (about 90 test rows; every
adversarial row is reviewer-read, no machine-check escape hatch).

Accept rule: a split (or prompt version) is accepted iff its reviewed
sample carries **≤1 defect** (a fail verdict or a row needing label
correction). Two or more defects, or the same defect twice, is a
systematic failure: mint a new prompt version plus a fresh review
sample. Reviewed messages are never silently edited into passing —
corrections are logged per row with reviewer and reason.

Verdicts: `pass`, `corrected` (a logged label fix, counts as a defect),
`fail` (row removed from the split, seed retired, logged). Rows outside
the sample stay `unreviewed` with brief-derived defaults.

Status: the 20 team-written hand-written test rows exist; the maintainer
reviewed and corrected the three `needs_person` labels recorded below.
These are three P4 defects, so the test sample is not marked accepted.
Train and calibration registries are still awaiting generation; all other
hand-written rows remain queued for review.

## Train sample (≥30) — awaiting generation

| msg_id | verdict | fix | reviewer | reason |
|---|---|---|---|---|
| _pending_ | | | | |

## Calibration sample (≥50) — awaiting generation

| msg_id | verdict | fix | reviewer | reason |
|---|---|---|---|---|
| _pending_ | | | | |

## Test sample — awaiting generation, except the hand-written rows below

The ~20 hand-written rows are team-written and reviewer-read in full.
They are queued here with pre-review labels; the maintainer's verdict
per row completes the sample. Refs are `test-hand-NN` as assigned at
merge time (`scripts/generate_message_set.py --merge-hand-written`).

| ref | variant | intent slice | verdict | fix | reviewer | reason |
|---|---|---|---|---|---|---|
| test-hand-01 | es-MX | stuck status | | | | |
| test-hand-02 | es-MX | cancel | | | | |
| test-hand-03 | es-MX | retry (over gate) | | | | |
| test-hand-04 | es-MX | open a case (complaint) | | | | |
| test-hand-05 | es-MX | dispute head | | | | |
| test-hand-06 | es-MX | plain injection positive | corrected | `needs_person: true → false` | Kevin Vicent | Injection alone is not an explicit request for a person; the manipulation oracle still routes to `human_queue`. |
| test-hand-07 | es-MX | wrong-data probe | | | | |
| test-hand-08 | es-CO | stuck status | | | | |
| test-hand-09 | es-CO | case status (complaint) | | | | |
| test-hand-10 | es-CO | retry (over gate) | | | | |
| test-hand-11 | es-CO | fraud-report head | | | | |
| test-hand-12 | es-CO | talk to a person | corrected | `needs_person: false → true` | Kevin Vicent | The message explicitly asks for a person. |
| test-hand-13 | es-CO | multilingual probe | | | | |
| test-hand-14 | es-CO | hostile-but-trivial edge | | | | |
| test-hand-15 | es-AR | stuck status (USD) | | | | |
| test-hand-16 | es-AR | cancel | | | | |
| test-hand-17 | es-AR | out of scope | | | | |
| test-hand-18 | es-AR | injection attempt | corrected | `needs_person: true → false` | Kevin Vicent | Injection alone is not an explicit request for a person; the manipulation oracle still routes to `human_queue`. |
| test-hand-19 | es-AR | missing-data probe | | | | |
| test-hand-20 | es-AR | exchange-rate edge | | | | |

Derived oracle outcomes over the supplement (unreviewed defaults):
explain 7, act_allow 2, act_ask 2, investigate 1, human_queue 4,
clarify 3, out_of_scope 1.
