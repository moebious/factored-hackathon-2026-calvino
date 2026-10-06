# T-107: Maintainer gold annotation and agreement report

| | |
|---|---|
| Wave | 1 |
| Branch | `feat/t107-gold-annotation` |
| Depends on | T-103 |
| Blocked by | — |
| Model | maintainer review (judgment checkpoint) |
| Can run in parallel | no |
| Specification | [TSD-031](../specs/TSD-031-gold-label-annotation.md) |
| References | TSD-015; TSD-019; TSD-013; decision 16 |

**Goal.** Complete the first 50 maintainer-reviewed gold cases and publish
the single-annotator consistency report. This is a System 3 task. Disclosed
model drafts inform classifier labels and, under decision 47, the oracle
facts and human outcomes; a maintainer must review and explicitly approve
every final value, and each value keeps its drafter named.

**Inputs.** `tests/fixtures/gold/gold-050.jsonl`, the classifier-label
worksheet at `docs/templates/T-107-gold-classifier-labels.csv`, the
outcome worksheet at `docs/templates/T-103-gold-outcome-annotations.csv`,
rubric v1, and the TSD-013 outcome oracle.

**Outputs.** All 50 classifier-label rows reviewed by the maintainer;
explicit `oracle_facts` and `human_outcome` annotations; and the agreement
report at `reports/eval/T-103-gold-agreement.md` with its reviewed
disagreement ledger at `reports/eval/T-103-gold-disagreements.md`.

**Open parameters.** none

**Done when.**

- All 50 classifier-label rows are complete and reviewed. The 18 existing
  labels are recorded as maintainer-only; all 32 model-drafted proposals
  receive explicit maintainer review. No values are guessed or auto-filled.
- Every row has complete, valid oracle facts and a rubric-based human
  outcome written in the specified review order by the drafter named in
  `outcome_annotator`, explicitly reviewed by the maintainer
  (decision 47).
- The classifier-label worksheet preserves all existing labels. Its
  importer previews by default and applies only explicit maintainer values.
- The report states the completeness count and `scored n/50`, numerator
  and denominator, exact agreement, single-annotator scope, and limits of
  the result. It reports kappa only when defined.
- The README, agreement report and disagreement ledger identify the 32
  model-drafted labels as maintainer-reviewed, name Claude Sonnet 5.5
  (`claude-sonnet-5-5`) in Claude Code on 2026-10-05, and disclose prior
  exposure and anchoring risk. They do not claim blind or independent
  human labels.
- The same three artifacts name `mimo-v2.6-flash-free` (OpenCode,
  2026-10-05) as the drafter of the oracle facts and human outcomes
  (decision 47) and state that the agreement figure is that drafter's
  consistency with the hand-written table, not independent maintainer
  consistency.
- The maintainer reviews and classifies every disagreement as a rubric
  gap, oracle mapping bug, or label slip, and records its resolution.
- Gold annotations remain held out from training and calibration. No
  dataset record is added or claimed; the existing rows use nominal
  scenario facts.

## Review workflow

1. Review the 32 proposal rows in the git-ignored file
   `data/T-107-proposals-DRAFT.csv`. Then enter your accepted or corrected values in
   `data/T-107-gold-classifier-labels.csv`. The sheet carries forward the
   18 existing labels and leaves missing cells blank. Use
   `gold/rubric-v1.md`; unclear cases are flagged, never guessed.
2. Preview the label import with
   `uv run python scripts/import_gold_labels.py --csv data/T-107-gold-classifier-labels.csv`.
   Review the proposed diff. Apply only after confirming the maintainer's
   entries with `--apply`.
3. Copy `docs/templates/T-103-gold-outcome-annotations.csv` to
   `data/T-103-gold-outcome-annotations.csv`. Complete the separate outcome
   worksheet in the TSD-015 review order. Preview and apply it with
   `uv run python scripts/import_gold_annotations.py --csv data/T-103-gold-outcome-annotations.csv`.
4. Run `uv run python scripts/report_gold_agreement.py --run-date YYYY-MM-DD --git-sha SHA`.
   The report lists incomplete rows and scores only complete, valid
   annotations.
