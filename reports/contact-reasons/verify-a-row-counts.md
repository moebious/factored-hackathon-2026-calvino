# Item A: row counts per table [measured]

Source: live `data/` prefix. Dedup on the primary key (first row kept); orphans are non-null foreign keys whose parent row is missing after the parent's own cleaning. Null foreign keys are kept.

| table | raw rows | duplicate PKs | orphan rows dropped | clean rows | null FKs kept |
|---|---:|---:|---:|---:|---|
| customers | 150,000 | 0 | 0 | 150,000 | - |
| branches | 350 | 0 | 0 | 350 | - |
| marketing_campaigns | 200 | 0 | 0 | 200 | - |
| daily_exchange_rates | 13,164 | 0 | 0 | 13,164 | - |
| service_agents | 1,200 | 0 | 0 | 1,200 | - |
| products | 400,000 | 0 | 0 | 400,000 | - |
| call_center_interactions | 686,296 | 0 | 0 | 686,296 | - |
| call_transcripts | 171,321 | 0 | 0 | 171,321 | - |
| complaints | 67,095 | 0 | 0 | 67,095 | affected_product_id: 22,525, related_branch_id: 47,917, origin_interaction_id: 67,095, assigned_agent_id: 23,115 |
| satisfaction_surveys | 212,759 | 0 | 0 | 212,759 | - |
| transactions | 4,425,008 | 0 | 0 | 4,425,008 | branch_id: 3,037,076 |
| campaign_sends | 1,746,801 | 0 | 0 | 1,746,801 | - |
| digital_events | 15,620,994 | 0 | 0 | 15,620,994 | customer_id: 3,745,446, product_id: 14,180,656 |
| **total (13 tables)** | **23,495,188** | | | **23,495,188** | |

Not applied: `service_agents.assigned_branch_id` -> `branches.branch_id`: 2 of 833 non-null values exist in the parent (0.24%); 833 distinct values against 350 branches. Every other foreign key has 0 orphans against its raw parent.

Analyst's lakehouse: 878,336 rows, 826 complaints. Full data: 26.7x the rows, 81.2x the complaints.

## Subset search for 878,336 rows and 826 complaints

Rows per country (customer-linked tables, reference tables excluded; reference tables hold 164,914 rows):

- Argentina: 3,899,239
- Colombia: 5,896,224
- México: 9,789,365

Contiguous date windows whose total equals 878,336:

- partitioned tables only: none
- plus reference tables: none

Complaint subsets (one or two attributes) with exactly 826 rows: [(('country', 'reception_channel'), ('Colombia', 'Branch'))]

Subsets tested: 2,149. One exact hit among that many groups of this size range is what chance produces; it is not evidence of a link.

Within +-8 rows of 826: [(('year', 'currency'), ('2026', 'ARS'), 822), (('year', 'currency'), ('2026', 'USD'), 830), (('month', 'priority'), ('2026-02', 'Medium'), 823), (('priority', 'reception_channel'), ('Low', 'Branch'), 829), (('currency', 'reception_channel'), ('MXN', 'Web'), 820), (('currency', 'is_repeat_complainer'), ('COP', 'True'), 827), (('currency', 'is_repeat_complainer'), ('MXN', 'True'), 827)]

