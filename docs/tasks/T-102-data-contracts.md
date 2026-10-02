# T-102: Data contracts, quality report and lineage

| | |
|---|---|
| Wave | 1 |
| Branch | `data/contracts` |
| Depends on | T-000 |
| Blocked by | dataset access |
| Model | standard model |
| Can run in parallel | yes |
| References | DESIGN.md 8.2; PRD NFR-2 |

**Goal.** Make data preparation checkable: contracts at every boundary, a quality report, lineage.

**Inputs.** the analyst's Parquet lakehouse (`clean_all_tables.py --all` on the full `data/` prefix; the two-week pilot window is a development subset only); the findings in DATA.md

**Outputs.** raw and clean contracts in `contracts/data/`, a validator, a generated quality report, lineage records

**Open parameters.** the cleaned layer's exact schema (from the analyst's delivery); known defects are reported, not cleaned away (for example the `service_agents` branch link). Contracts encode the handling rules in DATA.md: `Mexico` merged into `México` (ISO 3166 MX); a null `response_code` allowed in every status and never read as a failure; `claimed_amount` checked per currency and converted to USD before aggregation; complaints carry no `origin_interaction_id`

**Done when.** the validator runs on the tables in use and the report shows violation counts per rule; tests on a synthetic fixture

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
