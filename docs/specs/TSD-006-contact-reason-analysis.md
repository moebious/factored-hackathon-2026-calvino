# TSD-006: Contact-reason analysis and workflow decision rule

| | |
|---|---|
| Status | draft · **decision rule fixed before any data was examined** · [amendment 1](#amendment-1-2026-10-02) (2026-10-02) adapts it to the data's coarse reasons before any metric was computed; where they conflict, the amendment wins |
| Branch | `eval/contact-reasons` |
| Depends on | TSD-000 (for the package), dataset access |
| Required by | everything workflow-specific (labels, tools, cards, evaluation) |
| Requirements | BRD 2–3; brief item 1 ("a problem supported by data") |
| Design | DESIGN.md 7, 8; decision 5 (workflow: open) and 12 (ISO 20022 fit) |

## Purpose

Choose the one customer service workflow Calvino solves, **from the data**, using a rule written down before the data was examined. The rule exists so the data decides, not preference or hindsight. Anything in this file changed after the analysis starts must be listed under [Deviations](#deviations) with the reason.

## Candidates

| Candidate | Covers | ISO 20022 fit |
|---|---|---|
| **W1. "Where's my money"** | transfer and payment status, pending, declined or reversed debits, unrecognized account debit opening an investigation | strong: pacs.002, camt.053/054, camt.027/029 |
| **W2. Card problem journey** | declined card, unrecognized card charge, blocking a card, card dispute | partial: cards mostly use ISO 8583 |
| **W3. Complaint follow-up** | status, SLA and next steps of an existing complaint | weak |
| Excluded: credit eligibility | the brief adds a separate eligibility-policy requirement and regulatory risk | — |

## Procedure

1. **Map reasons blind.** List the distinct values of `contact_reason` and `reason_category` (names only, **no counts or metrics**). Map each value to W1, W2, W3 or "other" by meaning. Commit the mapping before computing anything. A value that fits two candidates is assigned to the one it most directly belongs to, and noted.
2. **Use deduplicated data.** Deduplicate on primary keys and drop orphan foreign keys first (or use the cleaned layer). If counts differ from the raw data by more than 5%, report both.
3. **Compute the evidence** per candidate, over the full date range, and again for the most recent 12 months as a trend check (reported, not scored).
4. **Apply the gates, then the score, then the tie-break**, exactly as below.
5. **Record the decision** in `docs/DECISIONS.md` (it closes decision 5), with the evidence table and any deviations.

## Evidence (per candidate)

From `call_center_interactions` (joined to `call_transcripts` and `customers`) and `complaints`:

| Metric | Definition |
|---|---|
| Volume share | interactions mapped to the candidate ÷ all interactions |
| Rank | best rank among the candidate's mapped reasons by volume |
| First-contact resolution (FCR) | share with `was_resolved = true` (nulls excluded and counted) |
| Escalation rate | share with `was_escalated = true` |
| Follow-up rate | share with `requires_followup = true` |
| Handle time | mean and median `duration_seconds` |
| Negative sentiment | share with `detected_sentiment` in (Negative, Very Negative) |
| Complaint share | complaints whose `category` maps to the candidate ÷ all complaints (mapped blind, as in step 1) |
| Transcripts | interactions with a transcript (`call_transcripts`) |
| Label balance | minority-class share of `was_escalated` within the candidate |
| Template check | 5-fold accuracy of a bag-of-words logistic regression predicting the mapped `contact_reason` from `customer_text` |

All results are reported with counts and denominators, overall and by country.

## Gates

A candidate is **out** if any gate fails:

| Gate | Passes when |
|---|---|
| G1. Demand | volume share ≥ 10%, **or** one of its reasons ranks in the top 5 by volume |
| G2. Room to improve | FCR below the overall FCR, **or** escalation rate above the overall rate |
| G3. Enough text | ≥ 2,000 transcripts |
| G4. Grounding | its answers and actions can be checked against dataset tables (W1: `transactions`; W2: `transactions`, `products`; W3: `complaints`) with at least 500 relevant records |

## Score

Weighted score on a 1–5 scale. Data criteria are scaled **across the candidates that passed the gates** (min-max to 1–5; with a single candidate, it scores 3 on each).

| # | Criterion | Weight | How it is scored |
|---|---|---|---|
| 1 | Demand and pain | 25% | weighted mean of scaled metrics: volume share 35%, FCR gap (overall − candidate) 20%, escalation gap (candidate − overall) 20%, handle time 10%, complaint share 10%, negative sentiment 5% |
| 2 | Fit with the thesis | 20% | fixed prior below |
| 3 | Grounding | 15% | fixed prior below |
| 4 | Labels | 15% | mean of scaled transcript count and label balance (closer to 50% is better); minus 1 (floor 1) if the template check exceeds 0.98 |
| 5 | ISO 20022 / MCP fit | 10% | fixed prior below |
| 6 | Demo clarity and safety | 10% | fixed prior below |
| 7 | Build risk | 5% | fixed prior below |

**Fixed priors** (set before the data; not revised by it):

| Candidate | Thesis | Grounding | ISO 20022 | Demo | Build risk |
|---|---|---|---|---|---|
| W1 "Where's my money" | 5 | 4 | 5 | 4 | 4 |
| W2 Card problem journey | 5 | 4 | 2 | 5 | 3 |
| W3 Complaint follow-up | 3 | 5 | 2 | 3 | 5 |

## Decision

1. The candidate with the highest score wins.
2. **Tie-break** (scores within 0.2): ISO 20022 fit, then lower build risk.
3. **If no candidate passes the gates:** take the candidate with the highest volume share among those passing G3 and G4, and report which gates failed and why.
4. **If the data shows a dominant reason that matches no candidate** (volume share ≥ 25% mapped to "other"): stop and bring it to the maintainer before deciding.

## Outputs

- `reports/contact-reasons/`: the blind mapping, the evidence tables (CSV), charts for the slides and analytics tab, and the scored decision. Aggregates only, never customer records.
- A short write-up for DECISIONS.md: winner, scores, gates, deviations.

## Tests and acceptance

- The analysis runs from a script with one command, against the cleaned layer or the raw data, reading the data location from environment variables.
- Unit tests on a tiny synthetic fixture for: the mapping application, gate evaluation, min-max scaling, the weighted score and the tie-break.

**Done when** the decision is recorded in DECISIONS.md with its evidence, and the maintainer has confirmed it.

## Deviations

Any change to the mapping procedure, gates, weights or priors after the analysis starts is listed here with its reason.

| # | Date | Change | Reason |
|---|---|---|---|
| 1 | 2026-10-02 | [Amendment 1](#amendment-1-2026-10-02): coarse mapping, W1/W2 attribution from structured tables, G1 and G3 redefined, the Labels criterion rescored, the template check reported instead of scored, stop rule applied per category | step 1 found that the data cannot support the original procedure (below) |

## Amendment 1 (2026-10-02)

### What step 1 found

Step 1 (listing names, no metrics) stopped the analysis, as the rule requires, because the data cannot separate the candidates as planned:

- `contact_reason` has the **same six values** as `reason_category`: Comercial, Producto, Queja, Retención, Transaccional, Técnico. There is no finer level.
- **Transcripts carry no label information.** 171,321 transcripts hold only **42 distinct `customer_text` values** (digits masked), and the same 42 appear under all six categories. They are built from two fixed openings (both balance enquiries, even under Queja and Técnico) plus generic closers. `detected_intents` has one value, `main_topics` repeats the six categories, `detected_keywords` has three generic tokens, `detected_language` is only `es` `[measured]`.
- `complaints` has 4 case types × 5 categories (Branch, Fees, Service, Technical, Transactions), with one subcategory each ("Cargo no reconocido" under Transactions).

Consequence: W1 and W2 both sit inside Transaccional, W3 maps loosely to Queja, and text-based evidence (G3, the Labels criterion, the template check) cannot discriminate. The text finding also changes how classifiers are trained and evaluated: see decision 16 in [DECISIONS.md](../DECISIONS.md).

**What was known when this amendment was written:** the distinct values above, the text structure, and one volume figure, Transaccional's share of interactions (about 35%). No other count, rate or metric had been computed. The fixed priors, weights and tie-break are unchanged.

### Amended procedure

**1. Category mapping (fixed here, by meaning).**

| `reason_category` / `contact_reason` | Maps to |
|---|---|
| Transaccional | **W1+W2 pool**, attributed to W1 or W2 by step 2 |
| Queja | **W3** |
| Comercial, Producto, Retención, Técnico | other |

Complaint share: the Transactions category → W1+W2 pool, attributed as in step 2 using the complaint's customer and date; Branch, Fees, Service, Technical → other. W3 follows up complaints of every category, so its complaint share is the share of complaints with `sla_breached = true`: the complaints where a follow-up is most needed.

**2. W1/W2 attribution from structured tables.** Before computing anything, list the distinct values of `transactions.transaction_type` and `transactions.channel` (names only) and map each pair to **W1** (account payments and transfers) or **W2** (card use) by meaning; commit that mapping. A **problem transaction** is one with `transaction_status` in (Declined, Pending, Reversed) or `is_fraud = true`. Then, for each Transaccional interaction:

- look at the same customer's problem transactions in the **7 days before** the interaction;
- attribute it to **W1** if all of them are W1-type, **W2** if all are W2-type, **both** if mixed, **unattributed** if none.

Interaction metrics (FCR, escalation, follow-up, handle time, sentiment, label balance) are computed per attributed group; W1's figures include "both".

*Fallback:* if fewer than 20% of Transaccional interactions are attributed, W1 and W2 get the pool's interaction metrics, and their volume shares are the pool share split in proportion to the counts of W1-type and W2-type problem transactions. Shares and metrics obtained this way are labelled **estimated**, and the identical metrics are reported as a limitation.

**3. Gates (G1 and G3 replaced).**

| Gate | Passes when |
|---|---|
| G1. Demand | volume share ≥ 10% (estimated for W1 and W2 under the fallback). The top-5 rank clause is dropped: with six categories it passes trivially |
| G2. Room to improve | unchanged |
| G3. Enough records | ≥ 2,000 interactions attributed to the candidate (under the fallback: ≥ 2,000 problem transactions of the candidate's type) |
| G4. Grounding | unchanged |

**4. Score.** Weights and fixed priors unchanged. Criterion 1 (demand and pain) uses the amended inputs. Criterion 4 (labels) becomes the scaled label balance alone: transcript count is dropped, because classifier text is team-generated for every candidate (decision 16) and no longer differs between them.

**5. Template check.** Still computed and reported as a data-quality finding; it no longer affects the score.

**6. Stop rule (decision step 4), per category.** Stop and bring it to the maintainer if any **single** category mapped to "other" has a volume share ≥ 25%. The aggregate "other" share is reported, not used as a trigger, because four of the six coarse categories fall outside every candidate by construction.

**7. Outputs** add the W1/W2 attribution: the transaction-type mapping, the attribution coverage, and whether the fallback was used.
