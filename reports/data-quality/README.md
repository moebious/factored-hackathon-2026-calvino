# Data-quality report [measured]

Ten findings on the full live `data/` prefix, deduplicated (no duplicate primary key exists). Every number is `[measured]`; aggregates only. Reproduce with `python scripts/analysis/data_quality.py` (CSV per finding next to this file). Country is the customer's country. The chance checks use 100 permutations.

## 1. Templated transcripts

**What it is.** Call transcript text is assembled from a handful of fixed pieces and says nothing about why the customer called.

**Query.** `SELECT reason_category, COUNT(*), COUNT(DISTINCT lower(regexp_replace(customer_text, '[0-9]', '#'))) FROM call_transcripts JOIN call_center_interactions USING (interaction_id) GROUP BY 1`

**Number.** 42 distinct `customer_text` values (digits masked) in 171,321 transcripts (0.025%); 42 of 42 texts appear under all 6 reason categories. `f01-templated-transcripts.csv`.

**Consequence for Calvino.** Transcripts cannot train or evaluate a reason classifier: text predicts the template, not the reason. Classifier text must be team-generated (decision 16).

## 2. Templated complaint descriptions

**What it is.** Complaint descriptions are a function of the category.

**Query.** `SELECT category, COUNT(*), COUNT(DISTINCT lower(regexp_replace(description, '[0-9]', '#'))) FROM complaints GROUP BY 1`

**Number.** 5 distinct descriptions in 67,095 complaints (0.007%); 5 of 5 belong to exactly one category. `f02-templated-complaint-descriptions.csv`.

**Consequence for Calvino.** Free text adds nothing beyond `category`; complaint features must come from the structured fields.

## 3. One reason level

**What it is.** `contact_reason` repeats `reason_category`; there is no finer level.

**Query.** `SELECT COUNT(DISTINCT reason_category), COUNT(DISTINCT contact_reason), SUM(contact_reason = reason_category) FROM call_center_interactions`

**Number.** 6 distinct values in both columns; 686,296 of 686,296 rows identical. `f03-reason-levels.csv`.

**Consequence for Calvino.** Reasons cannot separate workflow candidates (for example payment status from card problems): both sit inside `Transaccional`.

## 4. Independent fields

**What it is.** Fields that should be linked behave as independent: every type x channel pair exists, and problem transactions neither follow nor precede errors or calls more than chance.

**Query.** `pairs: SELECT transaction_type, channel, COUNT(*) FROM transactions GROUP BY 1,2; links: observed rate against permutations shuffling event timestamps within customer`

**Number.** 36 of 36 type x channel pairs present (`f04a`). Within 15 minutes, a problem transaction meets an Error event: 16 of 354,327 (0.0045%) against a permutation mean of 0.0037% (p95 0.0051%); on `/payments`: 4 of 354,327, permutation mean 0.0008%. An interaction has a same-customer problem transaction in the 7 days before: 1.48% observed against 1.48% permuted (1.00x); `Transaccional`: 1.48% against 1.49% (1.00x). Method: 100 permutations that shuffle timestamps among the same customer's events, which keeps each customer's activity but breaks any link. `f04c-chance-checks.csv`; supporting error rate per page in `f04b-error-rate-by-page.csv`: /transactions 6.0%, /transfer 6.0%, /payments 6.0%, /help 4.6%, and 0% on login, logout and product detail pages.

**Consequence for Calvino.** Attributing calls to payment or card problems from prior transactions would work at chance rate; links between tables cannot label scenarios. Scenarios and labels must be team-generated.

## 5. Uniform response_code nulls

**What it is.** `response_code` is null at the same rate in every transaction status, approved ones included.

**Query.** `SELECT transaction_status, COUNT(*), SUM(response_code IS NULL) FROM transactions GROUP BY 1`

**Number.** null share: Approved 5.00% (203,369 of 4,070,681), Declined 4.95% (10,962 of 221,234), Pending 4.97% (4,392 of 88,343), Reversed 5.16% (2,310 of 44,750); overall 221,033 of 4,425,008. `f05-response-code-nulls-by-status.csv`.

**Consequence for Calvino.** A missing response code is not a failure signal: do not use it as a feature or rule.

## 6. Broken foreign key

**What it is.** `service_agents.assigned_branch_id` points to branch ids that do not exist in `branches`. Reported only; no row is deleted.

**Query.** `SELECT COUNT(*), SUM(b.branch_id IS NOT NULL) FROM service_agents a LEFT JOIN branches b ON a.assigned_branch_id = b.branch_id WHERE a.assigned_branch_id IS NOT NULL`

**Number.** 2 of 833 non-null values exist in `branches` (0.24%); 833 distinct values against 350 branch rows. `f06-broken-foreign-key.csv`.

**Consequence for Calvino.** Agents cannot be joined to branches; do not cascade cleaning from this link (it would delete most agents and the interactions that reference them).

## 7. complaints.origin_interaction_id empty

**What it is.** No complaint records the interaction that caused it.

**Query.** `SELECT COUNT(*), SUM(origin_interaction_id IS NULL) FROM complaints`

**Number.** 67,095 of 67,095 null (100.00%). `f07-origin-interaction-null.csv`.

**Consequence for Calvino.** Complaint follow-up must link by customer and time, not by interaction.

## 8. digital_events.customer_id null share

**What it is.** Part of the event stream is anonymous and cannot be tied to a customer.

**Query.** `SELECT channel, COUNT(*), SUM(customer_id IS NULL) FROM digital_events GROUP BY 1`

**Number.** 3,745,446 of 15,620,994 events (23.98%); by channel Android App 23.9%, Desktop Web 24.1%, Mobile Web 24.0%, iOS App 24.0%. `f08-digital-events-customer-null.csv`.

**Consequence for Calvino.** Session-based features cover only the identified share of events; anonymous activity cannot enter a customer's history.

## 9. claimed_amount in mixed currencies

**What it is.** Claim amounts are in four currencies and mostly null; an average across them is meaningless.

**Query.** `SELECT currency, COUNT(*), SUM(claimed_amount IS NULL), AVG(claimed_amount) FROM complaints GROUP BY 1; USD = claimed_amount * rate(currency -> USD, nearest earlier date)`

**Number.** overall 45,344 of 67,095 claims have no amount (67.58%). Per currency: (none): 45,319 complaints, amount null 97.7%, mean 2,560 native = nan USD; ARS: 5,402 complaints, amount null 5.0%, mean 2,529 native = 7.23 USD; COP: 5,456 complaints, amount null 4.8%, mean 2,505 native = 0.63 USD; MXN: 5,487 complaints, amount null 5.0%, mean 2,536 native = 149.11 USD; USD: 5,431 complaints, amount null 4.8%, mean 2,566 native = 2,566.23 USD. Rate direction: `exchange_rate` for `source -> USD` converts one unit of the source currency to USD, so amounts are multiplied (checked against `transactions.amount_usd / amount` for ARS and COP; MXN has no transaction to check). Rate coverage of claims with an amount: (none) 0.0% (0 exact date, 0 earlier date, 1,040 none), ARS 100.0% (5,131 exact date, 1 earlier date, 0 none), COP 100.0% (5,191 exact date, 1 earlier date, 0 none), MXN 100.0% (5,213 exact date, 2 earlier date, 0 none), USD 100.0% (5,172 exact date, 0 earlier date, 0 none). `f09-claimed-amount-by-currency.csv`.

**Consequence for Calvino.** Never average `claimed_amount` across currencies; convert to USD first and state the rate rule. Most claims carry no amount, so any amount statistic describes a minority.

## 10. Foreign transaction_country labels

**What it is.** Foreign country labels are spread evenly over customers of every country, and `Mexico` (no accent) sits next to `México`.

**Query.** `SELECT transaction_country, COUNT(*) FROM transactions GROUP BY 1; and customer_country x transaction_country`

**Number.** share of rows: México 47.59%, Colombia 29.14%, Argentina 19.61%, USA 0.92%, Spain 0.92%, Mexico 0.92%, Brazil 0.91%. `México` appears for 0 non-Mexican customers; `Mexico` has 40,515 rows, from customers of México (18,412), Colombia (13,208), Argentina (8,895). The label differs from the customer's country on 221,212 of 4,425,008 rows (5.00%), or 202,800 (4.58%) if `Mexico` is merged into `México`. `f10a-transaction-country-share.csv`, `f10b-customer-country-by-transaction-country.csv`.

**Consequence for Calvino.** A cross-border rule on `transaction_country` sees no real signal (the foreign share is random) and must decide what `Mexico` means for Mexican customers: merging it turns those rows domestic. Brazil appears only as such a label; there is no BRL or Brazilian customer.

