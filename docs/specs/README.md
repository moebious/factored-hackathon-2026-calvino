# Technical specifications (TSD)

One spec per work stream and pull request: interfaces, data models, behaviour, tests and when it is done. Status and order of work live in one place, the [task backlog](../tasks/README.md); requirements are in [PRD.md](../PRD.md) and the design in [DESIGN.md](../DESIGN.md).

- [TSD-000](TSD-000-scaffolding.md): Python scaffolding and shared types
- [TSD-001](TSD-001-policy-engine.md): policy engine
- [TSD-002](TSD-002-mcp-tools.md): MCP tools and ISO 20022-aligned contracts
- [TSD-003](TSD-003-deployment.md): deployment skeleton
- [TSD-004](TSD-004-verifier.md): verifier framework
- [TSD-005](TSD-005-laya-service.md): Laya service and calibration
- [TSD-006](TSD-006-contact-reason-analysis.md): contact-reason analysis (superseded by decision 17)
- [TSD-007](TSD-007-data-contracts.md): data contracts, audit and lineage
- [TSD-008](TSD-008-gradio-demo.md): Gradio demo deployment adapter
- [TSD-009](TSD-009-hub.md): Calvino hub
- [TSD-010](TSD-010-customer-app.md): customer app with Laya cards
- [TSD-011](TSD-011-llm-client.md): LLM client and Hetzner provider
- [TSD-012](TSD-012-deploy-demo.md): deploy the demo at `calvino.rubrica.dev`
- [TSD-013](TSD-013-end-to-end-evaluation.md): end-to-end evaluation (T-303)
- [TSD-014](TSD-014-full-data-inventory.md): read-only full-data inventory
- [TSD-015](TSD-015-labels-splits.md): labels, splits and gold-set rubric (T-103, proposed)
- [TSD-016](TSD-016-support-agent.md): support agent, the LLM language work in the hub (T-301, proposed)
- [TSD-017](TSD-017-readme-results.md): README usage and results (T-501, proposed)
- [TSD-018](TSD-018-human-baseline.md): full-data human baseline (T-104)
- [TSD-019](TSD-019-message-set.md): team-generated customer message set (T-106, accepted)
- [TSD-020](TSD-020-laya-fine-tuning.md): Laya fine-tuning (T-202, accepted)
- [TSD-021](TSD-021-freshness-fixture.md): update-correctness fixture (T-105, proposed)
- [TSD-022](TSD-022-intent-driven-customer-app.md): intent-driven customer app and visual investigation (T-207, implemented)
- [TSD-023](TSD-023-operator-console.md): operator workspace and audit timeline (T-302, proposed)

Later tasks write their spec from their task card as the first step, numbered from TSD-024, and wait for the maintainer's approval before any code.

**Implementing a spec:** start the session with the prompt template in [tasks/README.md](../tasks/README.md#session-prompt-template). [AGENTS.md](../../AGENTS.md) holds every rule (branches, commits, tests, data, pushing). If a spec is wrong or incomplete, propose a change to the spec rather than diverging from it.
