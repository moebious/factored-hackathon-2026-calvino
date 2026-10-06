# Datasheet: Portuguese slice (TSD-032, T-203)

## What it is

`portuguese.json` holds 175 synthetic cases for a test-only Portuguese evaluation.
All 175 are labelled synthetic, written by the team and drafted with a model.

| Part | Count | Notes |
|---|---|---|
| Translated pairs | 150 | 50 frozen Spanish cases (`AC-*`, `ORC-*`, `ADV-*`, `EDGE-*`), each in 3 variants |
| Directly written | 25 | Portuguese-first, not derived from a Spanish message |

The three variants per source are standard Brazilian, colloquial Brazilian and formal
European Portuguese. They are three phrasings of the same 50 requests, not 150
independent scenarios. Report pair results with 50 as the number of distinct facts
(see Limitations).

## Why it exists

The bank dataset has no Portuguese text and no Brazilian customer (DATA.md, decision 16).
The brief requires Spanish and Portuguese. Pairs repeat the Spanish case's facts, persona,
script and `must_not`, so a changed route can be traced to language, not to a different
payment (T-405).

## Rules the data follows

- Speakers are modelled as customers of MX, CO, AR or the US. No BRL, `R$`, pix or boleto.
- A translation changes the message only. Facts, persona, resume script, `must_not` and
  entry references equal the source's. Tests enforce this.
- Empty, symbols-only and emoji-only edge cases are language-neutral, so their Portuguese
  message equals the Spanish one by design.
- Direct cases use only entries that exist in `tests/fixtures/bank/synthetic_bank.json`,
  with the fixture's status.
- Test only. No row is used for training, calibration, thresholds or the flywheel. The
  fine-tuning guard compares message text against this directory, and a test checks that
  none of these messages appears in the message-set files.

## Review

`review-log.md` lists a verdict for every row. The pass was a model read of each
Portuguese message against its source (Claude Sonnet 5.5, 2026-10-05). It corrected 64
rows: about 40 pairs matched a different Spanish request than the one they cite, a few
dropped or added an entry reference, one used a Brazilian payment rail, and two direct
cases disagreed with the bank fixture. The maintainer sign-off column is empty until
filled in. No native Portuguese speaker has reviewed the text.

## Limitations

- Model-drafted, not native-speaker reviewed. Idiom, register and regional word choice
  can be off, and a model reading its own family's output shares its blind spots.
- 50 distinct facts. Variant rows share a source, so they are not independent samples.
  Group rates have wide intervals; small groups are inconclusive (decision 37).
- Only 9 cases are over the amount gate and 20 carry a fraud flag. Boundary rates rest
  on those counts.
- Source Spanish is the frozen 50-case suite. The message-set test split has no drafted
  text yet, so none of its messages are translated.
- Portuguese speakers are modelled as cross-border customers; no Brazilian bank flows,
  documents or institutions are represented.
- Stricter Portuguese thresholds (decision 22) change routes for policy reasons. The
  T-405 reports them separately from model-driven flips.
