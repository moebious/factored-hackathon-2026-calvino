# T-107 gold/oracle consistency report

- Run date: 2026-10-05
- Git SHA: 1829998
- Evidence: measured, single-annotator consistency with the TSD-013 oracle under nominal facts
- Outcome annotator: mimo-v2.6-flash-free (OpenCode), model-drafted 2026-10-05, reviewed and approved by maintainer Kevin Vicent
- Classifier labels complete: 50/50
- Existing maintainer-only classifier labels: 18
- Model-drafted proposal rows reviewed: 32/32
- Gold sheet: 50 rows; scored 50/50

Classifier-label provenance: 18 existing labels are maintainer-only; 32 were model-drafted proposals. They were drafted with Claude Sonnet 5.5 (`claude-sonnet-5-5`) in Claude Code on 2026-10-05. The maintainer saw the proposals before review, creating anchoring risk and reducing label independence. Do not describe these as blind or independent human annotations. Oracle facts and human outcomes are annotated by the outcome annotator named above, which must name the drafter (decision 47); agreement is consistency between that annotator and the table over the same facts, not inter-annotator agreement or independent validation.

This is not an independent benchmark or a real-world oracle error bound. It does not measure T-106 defaults, message labels or model predictions.

| Metric | Numerator | Denominator | Agreement |
|---|---:|---:|---:|
| Oracle outcome equals maintainer outcome | 50 | 50 | 100.0% |

Cohen's kappa: 1.0000 [descriptive]

## Confusion matrix

| Oracle outcome | Human outcome | Count |
|---|---|---:|
| act_allow | act_allow | 8 |
| act_ask | act_ask | 1 |
| act_block | act_block | 3 |
| clarify | clarify | 3 |
| explain | explain | 16 |
| human_queue | human_queue | 11 |
| investigate | investigate | 6 |
| out_of_scope | out_of_scope | 2 |

## Unscored rows

None.

## Disagreements

None among scored rows.
