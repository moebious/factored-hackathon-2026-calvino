# Technical specifications (TSD)

*How each part of Calvino is built. Each spec is the source of truth for one work stream and one pull request: it defines interfaces, data models, behaviour, tests and when it is done. Requirements are in [BRD.md](../BRD.md) and [PRD.md](../PRD.md); the design is in [DESIGN.md](../DESIGN.md); the order of work is in [ROADMAP.md](../ROADMAP.md).*

## Index

| Spec | Stream | Wave | Status | Depends on |
|---|---|---|---|---|
| [TSD-000](TSD-000-scaffolding.md) | Python scaffolding and shared types | 0 (first) | implemented | foundation PRs merged |
| [TSD-001](TSD-001-policy-engine.md) | Policy engine | 0 | implemented | TSD-000 |
| [TSD-002](TSD-002-mcp-tools.md) | MCP tools and ISO 20022-aligned contracts | 0 | implemented | TSD-000 |
| [TSD-003](TSD-003-deployment.md) | Deployment skeleton | 0 | draft | TSD-000 |
| [TSD-004](TSD-004-verifier.md) | Verifier framework | 0 | draft | TSD-000 |
| [TSD-005](TSD-005-laya-service.md) | Laya service and calibration | 0 | draft | TSD-000 |
| [TSD-006](TSD-006-contact-reason-analysis.md) | Contact-reason analysis and workflow decision rule | 1 | superseded by decision 17 | dataset access |
| [TSD-007](TSD-007-data-contracts.md) | Data contracts, validator and lineage (T-102) | 1 | implemented | TSD-000 |

Specs for later tasks are written from their task cards ([tasks/](../tasks/README.md)) as each task's first step; the workflow they build is decision 17 ([DESIGN.md 6.1](../DESIGN.md#61-the-workflow-stuck-payments-end-to-end)).

## Implementing a spec

A work session (human or coding agent) is started with one line:

> Implement `docs/specs/TSD-NNN-….md`, following AGENTS.md.

Rules for every implementation:

1. Read [AGENTS.md](../../AGENTS.md) completely and follow it: own branch and worktree, Conventional Commits as the maintainer, no AI-tool attribution, and **no push without the maintainer's explicit approval**.
2. Read the spec, then the DESIGN.md sections and decisions it references.
3. If `main` does not yet contain AGENTS.md and DESIGN.md, stop: the foundation pull requests must be merged first.
4. Build exactly what the spec says. If the spec is wrong or incomplete, say so and propose the change to the spec rather than silently diverging.
5. Tests must not need network access, a GPU or the real dataset. Never write credentials, bucket names or real customer data into the repository.
6. When done: run tests and linters, review the diff, then report the results and the exact push and pull request you propose (branch, title, description from the template). Wait for approval.
