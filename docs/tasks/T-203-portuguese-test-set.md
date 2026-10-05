# T-203: Portuguese test set

| | |
|---|---|
| Wave | 2 |
| Status | done |
| Branch | `feat/pt-test-set` |
| Depends on | T-106 |
| Blocked by | — |
| Model | standard model |
| Can run in parallel | yes |
| References | DESIGN.md 5.1, 8.1 |

**Goal.** Make Portuguese and fact-invariant Spanish/Portuguese pairs measurable with broad coverage of the stuck-payments intents and risk boundaries (decisions 22 and 37).

**Inputs.** held-out Spanish messages with labels (T-106)

**Outputs.** ~150–200 translated cases (labels carried over, pairs kept for counterfactual checks) and ~20–30 cases written directly in Portuguese, all labelled synthetic

**Open parameters.** none

**Constraints.** amounts in MXN, COP, ARS or USD and customers in MX, CO or AR: the data has no BRL and no Brazilian customer (DATA.md), so Portuguese speakers are modelled as customers of those countries

**Done when.** translated held-out pairs and directly written cases cover the workflow's routes and high-risk boundaries, have reviewed labels, are never used for training or calibration, and their synthetic provenance and limitations are documented. T-405 reports paired model and policy effects separately.

**Specification:** [TSD-032](../specs/TSD-032-portuguese-test-set.md) (implemented).
