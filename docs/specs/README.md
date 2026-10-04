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

Later tasks write their spec from their task card as the first step, numbered from TSD-015, and wait for the maintainer's approval before any code.
**Implementing a spec:** start the session with the prompt template in [tasks/README.md](../tasks/README.md#session-prompt-template). [AGENTS.md](../../AGENTS.md) holds every rule (branches, commits, tests, data, pushing). If a spec is wrong or incomplete, propose a change to the spec rather than diverging from it.
