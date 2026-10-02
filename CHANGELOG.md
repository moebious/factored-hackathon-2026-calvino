# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org).

## [Unreleased]

### Added

- Python package scaffold (TSD-000): `uv` project, shared types (`Route`, `GateVerdict`, `HumanAction`, `Stage`, `DecisionRecord`), the append-only decision log with a reader for replay, and a CI job running ruff and pytest.
- Analysis scripts (`scripts/analysis/`) and tests (`tests/analysis/`): table fetch from the data bucket, Parquet cache, verification of the data analyst's decision-matrix numbers, a data-quality report and an independent T-104 headline baseline.
- Aggregate reports on the full dataset (`reports/contact-reasons/`, `reports/data-quality/`, `reports/baseline/`): W1/W2 transaction mapping, ten data-quality findings with chance checks, and headline interaction and complaint metrics.

- Policy engine (TSD-001): `calvino.policy` with `decide_route`, `decide_gate` and `replay_decision`, the versioned `policy/v1.yaml` (thresholds as hypotheses, per-currency limits as policy assumptions), fail-closed handling of missing or malformed inputs, and records that hold every input read so decisions replay from the log.

### Changed

- The baseline finding and the data-quality findings reach the tasks: DATA.md gains baseline rows and handling rules (status from `transaction_status`, `Mexico` merged into MX, USD conversion, complaint linking, no BRL); decision 17 gains a note; PITCH slide 1, DESIGN.md 7 and T-303 target matching the human 91.5% on calls; PLAN cuts the flywheel first and never the investigate stage; TSD-002, T-102, T-203 and T-206 carry the matching rules.
- Branch names are checked against `<type>/<short-description>` by the `pre-push` hook and the `conventions` CI job; tool-specific notes removed from AGENTS.md and HANDOFF.
- Agents never open pull requests (AGENTS.md); the attribution checker also blocks Factory Droid trailers and footers; HANDOFF wording is agent-neutral.
- HANDOFF records the independent baseline finding (Transaccional calls are resolved first time 91.5% of the time) and the follow-up it needs.
- PLAN gains the cut order and protected measurements; the task backlog gains shared-file and pull-request rules and a session prompt template; HANDOFF records the analyst's round-two asks and three new pitfalls.
- Specs, roadmap, plan, task cards, README, PITCH, glossary and brief coverage brought in line with decisions 16 and 17, the Tier 0 scope and the tech stack; TSD-001, -003, -004 and -005 gain a workflow-context section; HANDOFF marks TSD-000 done.
- Workflow chosen (decision 17): stuck payments, end to end (explain, clarify, act under the Gate, investigate, follow up); the pre-registered rule (TSD-006) is marked superseded, and Tier 0 gains durable cases, policy replay, one flywheel turn and a bare-LLM ablation.
- Classifier text is team-generated (decision 16): the dataset transcripts hold 42 distinct texts shared by every category; task T-106 builds the message set.
- DATA.md records measured row counts and the full-data quality findings.
- Evaluation scored against a seeded oracle; TSD-002 specifies the stuck-payments tools; TSD-003 keeps cases and decisions on persistent storage.
- Docs aligned with the stuck-payments workflow: README workflow section, Laya question set, card catalog, use cases for follow-up and offline learning, and no remaining workflow placeholders.
- Handoff guide refreshed with the current state, the measured data findings, the pending workflow verification and an ordered list of next actions.

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
