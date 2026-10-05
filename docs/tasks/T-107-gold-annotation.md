# T-107: Maintainer gold annotation and agreement report

| | |
|---|---|
| Wave | 1 |
| Branch | `docs/gold-annotation` |
| Depends on | T-103 |
| Blocked by | — |
| Model | maintainer review (judgment checkpoint) |
| Can run in parallel | no |
| References | TSD-015; TSD-019; TSD-013; decision 16 |

**Goal.** Complete the first 50 human-reviewed gold cases and publish the
single-annotator consistency report. This is a System 3 task. An agent must
not supply, infer, or suggest annotation values.

**Inputs.** `tests/fixtures/gold/gold-050.jsonl`, the blank worksheet at
`docs/templates/T-103-gold-outcome-annotations.csv`, rubric v1, and the
TSD-013 outcome oracle.

**Outputs.** All 50 classifier-label rows reviewed by the maintainer;
explicit `oracle_facts` and `human_outcome` annotations; the agreement
report at `reports/eval/T-103-gold-agreement.md`; and the reviewed
disagreement ledger at `reports/eval/T-103-gold-disagreements.md`.

**Open parameters.** none

**Done when.**

- All 50 classifier-label rows are complete and reviewed; the remaining
  32 rows are not guessed or auto-filled.
- Every row has complete, valid oracle facts and a rubric-based human
  outcome entered by the maintainer in the specified review order.
- The report states the completeness count and `scored n/50`, numerator
  and denominator, exact agreement, single-annotator scope, and limits of
  the result. It reports kappa only when defined.
- The maintainer reviews and classifies every disagreement as a rubric
  gap, oracle mapping bug, or label slip, and records its resolution.
- Gold annotations remain held out from training and calibration. No
  dataset record is added or claimed; the existing rows use nominal
  scenario facts.
