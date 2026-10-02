# T-205: Customer app with Laya cards

| | |
|---|---|
| Wave | 2 |
| Branch | `feat/customer-app` |
| Depends on | T-003 |
| Blocked by | — |
| Model | standard model |
| Can run in parallel | yes |
| References | decision 10; PRD FR-7, FR-8, FR-12, FR-13 |

**Goal.** The demo link's main screen: cards chosen from a fixed catalog, a glass box, scenario buttons.

**Inputs.** the hub API (mock it until T-204 lands); the card catalog

**Outputs.** the 8 cards in PRD FR-7, the problem-payment picker for clarification, confirm buttons bound to actions, the glass-box panel, scenario buttons, ES / PT toggle

**Open parameters.** none: the card catalog is PRD FR-7

**Done when.** every PRD use case UC-1 to UC-5 and UC-7 can be shown from a scenario button

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
