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

**Goal.** Establish the baseline every result is compared against.

**Inputs.** Transaccional interactions and Transactions-category complaints, on the full data (the analyst computes it; an analysis session cross-checks the headline figures). Precursor complete: the TSD-014 read-only inventory re-confirmed the live counts with no drift (`reports/data-quality/full-inventory.md`).

**Outputs.** first-contact resolution, escalation, follow-up, handle and wait time and (if available) CSAT, overall and by country and segment; for complaints, resolution days, SLA breaches and compensation; claimed amounts per currency and in USD

**Open parameters.** none: Transaccional calls and Transactions-category complaints (decision 17)

**Done when.** numbers with counts and denominators in `reports/baseline/`, reproducible from one command

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
