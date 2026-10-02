# T-101: Contact-reason analysis and workflow decision

| | |
|---|---|
| Wave | 1 |
| Branch | `eval/contact-reasons` |
| Depends on | — |
| Blocked by | dataset access |
| Model | strong model or maintainer review (judgment checkpoint) |
| Can run in parallel | yes |
| References | [TSD-006](../specs/TSD-006-contact-reason-analysis.md); BRD 2–3 |

**Goal.** Choose the workflow from the data by applying the pre-registered rule.

**Inputs.** the dataset (interactions, complaints, customers, transactions for the W1/W2 attribution; products for grounding counts; transcripts only for the template check)

**Outputs.** category and transaction-type mappings, evidence tables and charts in `reports/contact-reasons/`; a new decision in DECISIONS.md closing decision 5

**Open parameters.** none: the rule is fixed in TSD-006

**Done when.** the maintainer confirms the decision and it is recorded with its evidence

Its full specification is [TSD-006](../specs/TSD-006-contact-reason-analysis.md); implement that directly.
