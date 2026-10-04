# T-104: Human baseline for the chosen workflow

| | |
|---|---|
| Wave | 1 |
| Branch | `eval/baseline` |
| Depends on | T-101 |
| Blocked by | — |
| Model | standard model |
| Can run in parallel | yes |
| References | BRD 3 |

**Goal.** Establish a reproducible, full-data human baseline for the chosen categories, with the limits of that comparison explicit.

**Inputs.** Transaccional interactions and Transactions-category complaints on the full data; compare against the independent headline cross-check in `reports/baseline/`. TSD-014 re-confirmed the live inventory (`reports/data-quality/full-inventory.md`). The analyst's further delivery will not arrive.

**Outputs.** first-contact resolution, escalation, follow-up, handle and wait time and (if available) CSAT, overall and by country and segment; for complaints, resolution days, SLA breaches and compensation; claimed amounts per currency and in USD

**Open parameters.** none: Transaccional calls and Transactions-category complaints (decision 17)

**Done when.** full-data call and complaint slices with counts, denominators and null handling are reproducible from one command and reconcile with the independent cross-check. The report says explicitly that these are **category-level baselines**, not case-matched comparisons: calls cannot be linked to their underlying transactions, and investigation time savings can only be projected.

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
