# TSD-031: Maintainer gold-label annotation workflow (T-107)

| | |
|---|---|
| Status | accepted; model-drafted classifier proposals and model-drafted outcome annotations require maintainer review (2026-10-05, decision 48) |
| Branch | `feat/t107-gold-annotation` |
| Depends on | TSD-015 (gold schema and rubric), TSD-019 (agreement contract) |
| Task | [T-107](../tasks/T-107-gold-annotation.md) |
| References | TSD-013; `gold/rubric-v1.md`; decision 16 |

## Goal

Give the maintainer a safe, local CSV workflow to finish classifier labels
and the separate oracle-consistency annotations for the first 50 gold
messages. The tools validate and apply only explicit maintainer entries.
Disclosed model drafts may inform classifier labels; only the maintainer
decides and enters each final label.

The committed gold file currently has 18 complete classifier-label rows
and 32 incomplete rows. The outcome worksheet is a separate pass and
contains no completed outcome annotations.

## Boundaries

- This spec owns the classifier-label worksheet and its importer.
- TSD-015 owns the label definitions, gold schema and rubric.
- TSD-019 owns the separate nominal-facts, human-outcome, report and
  disagreement-ledger contract.
- No dataset transcript or customer record is used or added.
- The maintainer supplies or explicitly approves all final classifier
  labels. The tool does not fill defaults or choose labels.
- Model drafts apply to classifier labels and, under decision 48, to
  oracle facts and human outcomes. Every value names its drafter
  (`annotator`, `outcome_annotator`); outcomes become gold only after
  explicit maintainer review, and no report presents them as
  maintainer-entered, blind or independent.

## Classifier-label worksheet

`docs/templates/T-107-gold-classifier-labels.csv` has one row per
`gold_id`, with columns:

`gold_id`, `message`, `language_variant`, `workflow_area`, `stuck_intent`,
`clear_enough`, `needs_person`, `injection`, `annotator`, `labelled_at`,
`notes`.

The committed starting sheet copies the 18 existing classifier-label
annotations and leaves missing values blank. The maintainer edits a local
copy at `data/T-107-gold-classifier-labels.csv`; `data/` is git-ignored.
Empty label cells mean “not entered.” The message and language columns are
identity checks, not editable annotations.

Use the TSD-015 rubric. Do not guess unclear labels. An unset workflow area
is only complete for the rubric's unclassifiable case, where it has a
`none` oracle intent, `clear_enough = no`, and no stuck intent. Other
workflow areas do not take a stuck intent.

The current 32 proposals were drafted with Claude Sonnet 5.5
(`claude-sonnet-5-5`) in Claude Code on 2026-10-05. The maintainer saw the
proposals before review. The README, agreement report and disagreement
ledger must state that the 18 existing labels are maintainer-only and the
32 proposed labels are model-drafted. They must disclose that prior
exposure creates anchoring risk and reduces label independence. Do not
call the review blind or independent. Accepted, corrected and rejected
proposals all count as proposal-exposed because the maintainer saw them
before entering the final value.

## Import behavior

`scripts/import_gold_labels.py` reads the local CSV and
`tests/fixtures/gold/gold-050.jsonl`.

- Preview is the default. It validates the whole worksheet and prints a
  proposed JSONL diff, new-field count and fully labelled-row count.
- `--apply` writes the validated JSONL through an atomic replacement.
- The worksheet must contain all 50 known ids exactly once. Message and
  language identity must match the source row.
- New values are checked against `GoldLabels`; existing non-empty label
  values and provenance cannot be replaced. Repeated imports are
  idempotent.
- The importer never changes oracle facts, human outcomes or disagreement
  resolutions.
- Tests use synthetic rows and temporary files only.

The existing `scripts/import_gold_annotations.py` remains the second-pass
importer for nominal oracle facts and human outcomes. It is also preview
only unless the maintainer passes `--apply`.

## Report

The T-107 report at `reports/eval/T-103-gold-agreement.md` states the
number of complete classifier-label rows and the number of complete,
scored oracle/human outcomes separately. It preserves the single-annotator
limit and reports only complete, valid outcome annotations. The
disagreement ledger retains maintainer classifications and resolutions.
Both artifacts disclose the classifier-label provenance split, the
proposal model identity/version and the anchoring caveat.
Oracle facts and human outcomes name their drafter in
`outcome_annotator` and carry decision 48's caveat: one drafter's rubric
application against the hand-written table, not independent maintainer
consistency.

## Done when

- The maintainer has reviewed all 50 classifier-label rows.
- All 50 rows have complete, valid nominal oracle facts and human
  outcomes written in the TSD-015 review order by the drafter named in
  `outcome_annotator` and explicitly reviewed by the maintainer.
- A preview shows no unintended changes before either importer is applied.
- The report shows `50/50` complete classifier-label rows and `scored
  50/50` outcomes, with all disagreements reviewed and recorded.
- Every final classifier label is entered or explicitly approved by the
  maintainer. The report states the 18/32 provenance split and anchoring
  caveat; it does not claim independent human annotation.
- Every oracle fact and human outcome names its drafter and has explicit
  maintainer review (decision 48); the report names the outcome drafter
  and does not present the agreement as independent human consistency. No
  customer records or dataset transcripts are added.
