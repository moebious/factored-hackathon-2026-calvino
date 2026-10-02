# Transaction (type, channel) mapping for W1/W2 attribution

Step 2 of Amendment 1 to TSD-006. Fixed from the distinct names alone, before any
count was computed.

Distinct values `[measured]`:

- `transaction_type`: Adjustment, Deposit, Payment, Purchase, Transfer, Withdrawal
- `channel`: ATM, App, Branch, POS, Transfer, Web
- `transaction_status`: Approved, Declined, Pending, Reversed
- All 36 (type, channel) pairs occur, so channel is independent of type in this data.

Candidates: **W1** = account payments and transfers; **W2** = card use. "excluded"
means the pair is never a problem transaction for either candidate.

| type \ channel | ATM | App | Branch | POS | Transfer | Web |
|---|---|---|---|---|---|---|
| Transfer   | W1 | W1 | W1 | W1 | W1 | W1 |
| Payment    | W2 | W1 | W1 | W2 | W1 | W1 |
| Purchase   | excluded | W2 | excluded | W2 | excluded | W2 |
| Withdrawal | W2 | excluded | excluded | W2 | excluded | excluded |
| Deposit    | excluded | excluded | excluded | excluded | excluded | excluded |
| Adjustment | excluded | excluded | excluded | excluded | excluded | excluded |

## Rationale

- **Transfer** is a transfer on any channel: W1.
- **Payment** is an account payment (W1) unless made at a card terminal (ATM, POS), where
  it is card use (W2).
- **Purchase** is card use (W2) where a card can be used: POS, App, Web. At ATM, Branch
  and the Transfer channel it is not plausible, so it is excluded.
- **Withdrawal** is card use (W2) at ATM and POS (cash-back). A teller or non-card
  channel withdrawal is excluded.
- **Deposit** and **Adjustment** are neither a payment, a transfer nor card use: excluded.
  Adjustments are bank-side corrections, not customer-initiated.

## Limits to report with the results

- The implausible pairs (for example Purchase on Branch) exist in the data and are
  excluded; the excluded share of problem transactions is reported with the counts.
- This is a judgement by meaning; no outcome was looked at when it was fixed.
