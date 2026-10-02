# Items D and E: complaint text and the fields the suite relies on [measured]

## D. Complaint free text

| measure | value |
|---|---|
| complaints | 67,095 |
| rows with a null `description` | 0 |
| distinct `description` values (digits masked) | 5 |
| distinct / rows | 0.007% |
| values shared across more than one `category` | 0 of 5 |
| values shared across more than one `case_type` | 5 of 5 |
| distinct `resolution` values | 6 |

Each of the five descriptions belongs to exactly one category, so the text is a function of `category` and adds no information beyond it.

## E. Columns

**transactions** (22 columns): `transaction_id`, `transaction_date`, `process_date`, `product_id`, `customer_id`, `transaction_type`, `transaction_category`, `amount`, `currency`, `amount_usd`, `channel`, `branch_id`, `merchant_name`, `merchant_category`, `transaction_country`, `transaction_city`, `transaction_status`, `response_code`, `is_fraud`, `fraud_score`, `latitude`, `longitude`

**digital_events** (26 columns): `event_id`, `event_date`, `process_date`, `customer_id`, `session_id`, `event_type`, `event_category`, `channel`, `platform`, `browser`, `app_version`, `page_url`, `page_title`, `action`, `element_id`, `product_id`, `event_value`, `duration_seconds`, `ip_address`, `ip_country`, `ip_city`, `is_mobile`, `referrer`, `utm_source`, `utm_medium`, `utm_campaign`

**complaints** (27 columns): `complaint_id`, `creation_date`, `process_date`, `customer_id`, `case_type`, `category`, `subcategory`, `reception_channel`, `affected_product_id`, `related_branch_id`, `origin_interaction_id`, `description`, `claimed_amount`, `currency`, `priority`, `status`, `assigned_agent_id`, `assignment_date`, `first_response_date`, `resolution_date`, `closing_date`, `sla_breached`, `resolution_days`, `resolution`, `compensation_granted`, `resolution_satisfaction`, `is_repeat_complainer`

### Field search over all 13 tables

Column names matching card, EMV, chip, 3DS, secure, CVV, PAN, BIN, IP, geo, latitude, longitude, Brazil or BRL:

- branches: `geographic_zone`, `latitude`, `longitude`
- call_center_interactions: none
- call_transcripts: none
- campaign_sends: none
- complaints: none
- customers: none
- daily_exchange_rates: none
- digital_events: `ip_address`, `ip_country`, `ip_city`
- marketing_campaigns: none
- products: none
- satisfaction_surveys: none
- service_agents: none
- transactions: `latitude`, `longitude`

No card table, and no EMV, chip, 3DS, CVV, PAN or BIN column in any table. Cards exist only as `products.product_type` values: `Tarjeta Crédito`, `Tarjeta Débito`.

### Brazil and BRL

- `BRL` in `transactions.currency`: 0; currencies present in `products`: ARS, COP, USD; in `transactions`: ARS, COP, USD.
- Customer and branch countries: Argentina, Colombia, México (no Brazil).
- `Brazil` appears as `transaction_country` on 40,472 of 4,425,008 transactions (0.91%), in currencies USD 20,726, COP 11,887, ARS 7,859.
- Cross-tab of customer country by `transaction_country` (rows):

| customer country | Argentina | Brazil | Colombia | Mexico | México | Spain | USA |
|---|---:|---:|---:|---:|---:|---:|---:|
| Argentina | 835,805 | 8,716 | 8,887 | 8,895 | 0 | 8,836 | 8,866 |
| Colombia | 13,401 | 13,260 | 1,262,197 | 13,208 | 0 | 13,122 | 13,384 |
| México | 18,355 | 18,496 | 18,419 | 18,412 | 2,105,794 | 18,584 | 18,371 |

Foreign countries (USA, Spain, Brazil, and the spelling variant `Mexico` next to `México`) each hold about 0.9% of transactions, spread evenly over customers of every country, and Brazil's problem-status rate is 7.8% against 8.0% elsewhere. Brazil is a label on a random foreign share, not a market in this data.

