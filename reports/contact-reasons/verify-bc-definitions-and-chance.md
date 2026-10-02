# Items B and C: definitions, counts and chance checks [measured]

Live `data/` prefix, deduplicated (no duplicate primary keys exist). Country is the customer's country unless stated.

## B. C1 'stuck payment'

### Problem transactions

Definition: `transaction_status` in (Declined, Reversed, Pending). Analyst: 4,520.

| scope | problem txns | all txns | share | vs 4,520 |
|---|---|---|---|---|
| all types | 354,327 | 4,425,008 | 8.01% | 78x |
| Payment or Transfer only | 130,772 | 1,635,402 | 8.00% | 29x |

| country | problem | all | share |
|---|---|---|---|
| Argentina | 70,669 | 880,005 | 8.03% |
| Colombia | 106,031 | 1,328,572 | 7.98% |
| México | 177,627 | 2,216,431 | 8.01% |

| status | rows |
|---|---|
| Approved | 4,070,681 |
| Declined | 221,234 |
| Pending | 88,343 |
| Reversed | 44,750 |

### Response-code nulls

Definition: `response_code` is null. Analyst: about 2,900 (64% of 4,520).

| status | response_code null | status total | null share |
|---|---|---|---|
| Approved | 203,369 | 4,070,681 | 5.00% |
| Declined | 10,962 | 221,234 | 4.95% |
| Pending | 4,392 | 88,343 | 4.97% |
| Reversed | 2,310 | 44,750 | 5.16% |

All nulls: 221,033 of 4,425,008; share of problem transactions with a null: 4.99%.

### Payment errors in digital_events

No error-code or message column exists. Definitions tried: A = `event_type = 'Error'` (any page); B = Error on `/payments`; C = Error with `action = 'initiate_payment'`. Analyst: about 2,800.

| definition | events | with customer_id | vs 2,800 |
|---|---|---|---|
| A: any Error | 358,723 | 272,663 | 128x |
| B: Error on /payments | 56,774 | 43,108 | 20x |
| C: Error + initiate_payment | 53,657 | 40,746 | 19x |

Definition B by `ip_country` (spelling variants merged):

| ip_country | payment errors (B) | all events |
|---|---|---|
| Argentina | 12,647 | 3,533,045 |
| Colombia | 17,492 | 4,806,882 |
| México | 26,635 | 7,281,067 |

Error rate by page (share of that page's events): /transactions 6.0%, /transfer 6.0%, /payments 6.0%, /help 4.6%, /home 4.5%, /products 4.5%, /accounts 4.5%, /login 0.0%, /products/credit-card 0.0%, /logout 0.0%, /products/savings 0.0%, /products/loans 0.0%

Errors are spread over every page, at 4.5% to 6.0% of events, so the payments page is not special.

## B. C2 'is this charge mine?'

Definitions: D1 = category `Transactions` (subcategory 'Cargo no reconocido'); D2 = D1 and `case_type = 'Claim'`. Analyst: 297 disputed charges, average claim about 2,600.

| definition | complaints | with amount | mean claim (currencies mixed) | median | mean in USD |
|---|---|---|---|---|---|
| D1 | 13,580 | 4,500 | 2,537 | 2,520 | 684 |
| D2 | 3,335 | 1,308 | 2,566 | 2,560 | 680 |

D2 per currency (the 'about 2,600' figure averages MXN, COP, USD and ARS amounts as if they were one unit):

| currency | claims | with amount | mean (native) | mean (USD) |
|---|---|---|---|---|
| ARS | 317 | 301 | 2,653 | 8 |
| COP | 337 | 326 | 2,516 | 1 |
| MXN | 318 | 302 | 2,610 | 153 |
| USD | 328 | 318 | 2,514 | 2,514 |

| country (customer) | D2 claims |
|---|---|
| Argentina | 685 |
| Colombia | 990 |
| México | 1,660 |

D2 has 3,335 rows against 297 (11x); all categories: 67,095 complaints.

## C. Chance checks

### Problem transaction to error event, +-15 minutes

Match: a problem transaction of customer X and an `Error` event (definition A, and definition B) of the same customer within 15 minutes either way. Null model: 100 permutations that shuffle all of a customer's event timestamps among that customer's events, then read off the Error events.

| error definition | matched problem txns | observed rate | permutation mean | permutation p95 | observed / mean |
|---|---|---|---|---|---|
| A: any Error | 16 of 354,327 | 0.005% | 0.004% | 0.005% | 1.23x |
| B: Error on /payments | 4 of 354,327 | 0.001% | 0.001% | 0.001% | 1.37x |

Control: an equal-size random sample of Approved transactions matches an Error event within 15 minutes at 0.003%.

### Interaction to problem transaction, 7 days before

Match: a same-customer problem transaction in the 7 days before the interaction. Null model: 100 permutations that shuffle interaction timestamps within customer. Compared by `reason_category`, because the attribution in TSD-006 assumes Transaccional interactions follow problem transactions.

| reason_category | interactions with a problem txn | observed | permutation mean | permutation p95 | observed / mean |
|---|---|---|---|---|---|
| all | 10,173 of 686,296 | 1.48% | 1.48% | 1.48% | 1.00x |
| Comercial | 799 of 54,879 | 1.46% | 1.44% | 1.51% | 1.01x |
| Producto | 2,271 of 150,863 | 1.51% | 1.48% | 1.52% | 1.02x |
| Queja | 1,708 of 117,021 | 1.46% | 1.48% | 1.53% | 0.98x |
| Retención | 329 of 20,578 | 1.60% | 1.48% | 1.60% | 1.08x |
| Transaccional | 3,562 of 240,056 | 1.48% | 1.49% | 1.52% | 1.00x |
| Técnico | 1,504 of 102,899 | 1.46% | 1.49% | 1.55% | 0.98x |

