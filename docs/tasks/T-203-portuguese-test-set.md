# T-203: Portuguese test set

| | |
|---|---|
| Wave | 2 |
| Branch | `data/pt-test-set` |
| Depends on | T-106 |
| Blocked by | — |
| Model | standard model |
| Can run in parallel | yes |
| References | DESIGN.md 5.1, 8.1 |

**Goal.** Make Portuguese measurable: a synthetic test set built from held-out Spanish messages.

**Inputs.** held-out Spanish messages with labels (T-106)

**Outputs.** ~150–200 translated cases (labels carried over, pairs kept for counterfactual checks) and ~20–30 cases written directly in Portuguese, all labelled synthetic

**Open parameters.** none

**Constraints.** amounts in MXN, COP, ARS or USD and customers in MX, CO or AR: the data has no BRL and no Brazilian customer (DATA.md), so Portuguese speakers are modelled as customers of those countries

**Done when.** never used for training or calibration; limitations documented

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
