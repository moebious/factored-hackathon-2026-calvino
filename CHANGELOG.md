# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org).

## [Unreleased]

### Added

- Full-data contract audit report (`reports/data-quality/contracts-audit.json` and a summary): all eight tables pass, every known defect matches DATA.md, and a 10,000-row sample per table passes the row models.
- Data contracts (TSD-007, T-102): row models and rules from DATA.md for the eight tables Calvino uses, a DuckDB audit over Parquet or CSV that reports known defects without failing, JSON Schemas and lineage in `contracts/data/`, and a synthetic lakehouse fixture.
- Python package scaffold (TSD-000): `uv` project, shared types (`Route`, `GateVerdict`, `HumanAction`, `Stage`, `DecisionRecord`), the append-only decision log with a reader for replay, and a CI job running ruff and pytest.
- Analysis scripts (`scripts/analysis/`) and tests (`tests/analysis/`): table fetch from the data bucket, Parquet cache, verification of the data analyst's decision-matrix numbers, a data-quality report and an independent T-104 headline baseline.
- Aggregate reports on the full dataset (`reports/contact-reasons/`, `reports/data-quality/`, `reports/baseline/`): W1/W2 transaction mapping, ten data-quality findings with chance checks, and headline interaction and complaint metrics.
- ADR-027 and Decision 27: Laya deployment on Hugging Face Spaces (`calvino-laya`) using Gradio SDK (16 GB RAM, $0.00 cost) with native FastAPI endpoints for Vercel, and decoupled GPU fine-tuning (Kaggle/Colab T4 in 3 min) exporting to Model Hub. Visual multi-criteria comparison report in `reports/comparativa_despliegue_laya.html`.

- Policy engine (TSD-001): `calvino.policy` with `decide_route`, `decide_gate` and `replay_decision`, the versioned `policy/v1.yaml` (thresholds as hypotheses, per-currency limits as policy assumptions), fail-closed handling of missing or malformed inputs, and records that hold every input read so decisions replay from the log.

- MCP tools (TSD-002): `calvino.tools` with ten stuck-payments tools built on the official MCP SDK, the `BankAdapter` protocol and a dataset adapter over a synthetic fixture, ISO 20022-aligned contracts as JSON Schema in `contracts/tools/`, a session attached by the hub (never a tool argument), single-use expiring confirmation tokens bound to one action, customer-scoped idempotency keys, stable refusal rule ids, and an adapter conformance suite.

### Changed

- README cut to the essentials (positioning, the five stages with a clean flow diagram, quick start, where to start); everything removed already lives in DESIGN, DATA, PITCH, AGENTS or the backlog; the specs index is shorter, with tasks and current statuses.
- `main-guard` asks again, up to six times ten seconds apart, before treating a commit without a merged pull request as a bypass: GitHub links commits to their pull request a few seconds after the merge, which turned `main` red after #24.
- Decisions 20–26: open models with a judge from another family, a veto-only verifier panel, stricter Portuguese thresholds until measured, acceptance scenarios in CI, the playbook file with per-stage tools, fairness lines, and integration directions with A2A only through the hub; ideas from the September 29 planning draft that were replaced are listed with reasons. DESIGN gains the positioning against three harness definitions, a full journey (6.2), the language coverage table, the latency split and the trusted test session; the backlog gains owners; T-303 lists every case the brief requires; PITCH sharpens positioning and limits; HANDOFF records the current state and new pitfalls.
- Agents plan their commits before coding and prefer small logical commits: AGENTS.md, the session prompt template and the PR template say so, and `scripts/git/check-commit-size.sh` enforces 15 files and 800 changed lines per commit (lock files and generated paths not counted; a `Size-exception:` footer opts out) in the `pre-push` hook and the `conventions` CI job.
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
