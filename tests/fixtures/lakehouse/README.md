# Synthetic lakehouse fixture (TSD-007)

**Synthetic.** Invented rows in the shape of the tables Calvino uses, for the data contract tests. No real customer, account or transaction.

The fixture passes the audit and carries one of each known defect from DATA.md, so the tests can check that each is counted and none fails the audit:

| Check | Rows |
|---|---|
| `TX-RESPONSE-CODE-NULL` (null `response_code`, one of them Approved) | 2 |
| `TX-COUNTRY-MEXICO` (unaccented `Mexico` label) | 1 |
| `CP-AMOUNT-NO-CURRENCY` | 1 |
| `CP-ORIGIN-NULL` | 3 |
| `CI-REASON-REPEATS` | 3 |
| `FK-assigned_branch_id` on `service_agents` (branch missing) | 1 |
