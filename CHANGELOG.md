# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org).

## [Unreleased]

## [0.1.0] - 2026-10-02

### Added

- Design document (`docs/DESIGN.md`): harness architecture, Laya System One classifiers with a deterministic policy floor, governance constraints, fairness, human-in-the-loop and evaluation plan, with evidence labels on claims.
- Decision log (`docs/DECISIONS.md`) and build plan (`docs/PLAN.md`).
- README with description, architecture diagram, roadmap and project status.
- `AGENTS.md` with repository standards, git conventions (Conventional Commits, branching, squash merges, versioning, authorship), data and secrets rules and Calvino design rules, plus a one-line import file so coding tools load it.
- Pull request template.
- `.editorconfig`, and a `.gitignore` covering OS, editor, Node, runtime and model-weight files.
- CI check (`conventions`) that enforces Conventional Commits on PR titles and commits and rejects AI-tool attribution.
- Versioned git hooks (`commit-msg`, and a `pre-commit` guard against datasets, `.env` files, model weights and credentials) sharing one checker script with CI, with tests.
- Worktree-per-branch workflow: hooks block commits on `main`, commits outside a linked worktree and pushes to `main`; a `main-guard` workflow flags commits that reach `main` without a merged pull request.
- Thesis restated as Systems 1, 1.5, 2 and 3 (Laya, the Calvino hub, agents with verifiers, humans), with the data flywheel and its safeguards; design gaps against the brief closed (out-of-scope outcome, retention, provenance, contracts and freshness, result labels).
- Decisions 9 to 15 (MCP boundary, glass-box demo link, operator console, ISO 20022-aligned contracts, hub and spoke, tiered verifiers, agent scope), the tier ladder, phase 2 detail and the roadmap of parallel work streams.
- Business and product requirements (BRD, PRD) and technical specifications for the wave 0 work streams (TSD-000 to TSD-005), linked across the docs.
- Handoff guide, task backlog and cards for every remaining task, the pre-registered workflow decision rule (TSD-006), rejected alternatives, brief coverage matrix, dataset summary, glossary, source summaries and pitch outline; the architecture diagram now shows Systems 1 to 3.

[Unreleased]: https://github.com/moebious/factored-hackathon-2026-calvino/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/moebious/factored-hackathon-2026-calvino/releases/tag/v0.1.0
