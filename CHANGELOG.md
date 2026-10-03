# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org).

## [Unreleased]

### Added

- LLM client and Hetzner provider (TSD-011, T-011, decision 28): `calvino.llm` with a provider-agnostic `ChatClient`, one OpenAI-compatible adapter (timeout, retries on 429 and 5xx, a requests-per-window limiter) and the Hetzner configuration for the agent role. The model id comes from the environment because the provider's `/v1/models` list is authoritative. The judge role is configured separately and `clients_from_env` refuses to start when both models share a family, which is how decision 20's judge independence survives a change to one environment variable.
- Language models are pinned and checkable (TSD-011, decision 29): `providers.yaml` records the model, provider, pin kind and observed catalogue per role, `calvino.llm.providers` compares a deployment against it, and `scripts/check_providers.py` also asks each provider what it serves and names the nearest ids when a configured model is gone. The check is a deploy gate, not a startup step, so a provider being briefly unavailable cannot take the demo link down.
- Full-data contract audit report (`reports/data-quality/contracts-audit.json` and a summary): all eight tables pass, every known defect matches DATA.md, and a 10,000-row sample per table passes the row models.
- Data contracts (TSD-007, T-102): row models and rules from DATA.md for the eight tables Calvino uses, a DuckDB audit over Parquet or CSV that reports known defects without failing, JSON Schemas and lineage in `contracts/data/`, and a synthetic lakehouse fixture.
- Python package scaffold (TSD-000): `uv` project, shared types (`Route`, `GateVerdict`, `HumanAction`, `Stage`, `DecisionRecord`), the append-only decision log with a reader for replay, and a CI job running ruff and pytest.
- Analysis scripts (`scripts/analysis/`) and tests (`tests/analysis/`): table fetch from the data bucket, Parquet cache, verification of the data analyst's decision-matrix numbers, a data-quality report and an independent T-104 headline baseline.
- Aggregate reports on the full dataset (`reports/contact-reasons/`, `reports/data-quality/`, `reports/baseline/`): W1/W2 transaction mapping, ten data-quality findings with chance checks, and headline interaction and complaint metrics.

- Policy engine (TSD-001): `calvino.policy` with `decide_route`, `decide_gate` and `replay_decision`, the versioned `policy/v1.yaml` (thresholds as hypotheses, per-currency limits as policy assumptions), fail-closed handling of missing or malformed inputs, and records that hold every input read so decisions replay from the log.

- MCP tools (TSD-002): `calvino.tools` with ten stuck-payments tools built on the official MCP SDK, the `BankAdapter` protocol and a dataset adapter over a synthetic fixture, ISO 20022-aligned contracts as JSON Schema in `contracts/tools/`, a session attached by the hub (never a tool argument), single-use expiring confirmation tokens bound to one action, customer-scoped idempotency keys, stable refusal rule ids, and an adapter conformance suite.

- Laya service and calibration (TSD-005, T-005): `calvino.classifiers` wrapping the real laya 0.3.24 router API pinned to the multilingual model (startup preload that fails fast when laya is absent), choice question builders with neutral binary keys, answers gated on laya's calibrated `answer_confidence` with `action.act_probability` stripped, temperature scaling fit per (question type, option count) with ECE and Brier before and after, a hand-rolled SVG reliability diagram, `scripts/run_calibration.py`, and a synthetic Spanish/Portuguese calibration fixture.

- Deployment skeleton (TSD-003, T-003): `calvino.api` FastAPI demo service (`/health`, `/ready`, `POST /api/demo/decide` behind a passcode and a per-client rate limit, fail closed without a configured passcode), the System 1 loader interface with a fake for tests and a production loader wrapping `LayaClient`, restart-durable storage on `CALVINO_DATA_DIR` proven by a restart test, a Hugging Face Space Dockerfile (non-root, port 7860, laya checkpoint baked at build time), a keep-alive workflow driven by a repository variable, the minimal Next.js demo frontend (warm-up screen, glass-box result, `/api/*` rewritten to `BACKEND_URL`), and `docs/DEPLOY.md` with the exact maintainer steps.

- Verifier framework (TSD-004, T-004): `calvino.verifier` with the versioned `customer-answer` rubric (`rubrics/customer-answer.yaml`, ten criteria partitioned across code, Laya and judge per DESIGN 4.4 and decision 17), evidence collected from the session's tool results, five deterministic code checks that err toward failing, the `Judge` and `LayaChecker` interfaces with a versioned prompt template that decomposes criteria into checklists and fails when unclear (`MockJudge` and `FakeLayaChecker` until the provider is chosen), and the cascade: fixed aggregation, model-tier errors counted as failures, one retry with the failed criteria as feedback, escalation with the failed criteria in the case file, and `DecisionRecord` logging carrying the rubric and prompt versions.

- Calvino hub (TSD-009, T-204): `calvino.hub` with the versioned stuck-payments playbook (`playbooks/stuck-payments.yaml`, per-stage tools and status guidance read by the agent prompt), trusted test sessions issued by the hub (the token never passes through a model), a LangGraph workflow over the policy verdicts with the five stages (explain, clarify, act, investigate, follow up), a Gate in front of every write (allow runs the tool with a single-use confirmation token and a verified read-back, ask parks the turn with `interrupt()` for the customer's approval, block refuses naming the rule), investigate opening a bank case behind the Gate with a handoff case file, `interrupt()` parking turns for the operator queue, the `HubService` facade with resume over a sqlite checkpointer, and the seeded acceptance scenarios (AC-1 to AC-4, AC-6, AC-8 as data in `tests/scenarios/`) with a scoreboard printed on every pytest run (decision 23).

- Customer app (TSD-010, T-205): the hub HTTP endpoints (`POST /api/hub/message`, `POST /api/hub/resume`, `GET /api/hub/personas` behind the demo passcode and the per-client rate limit; the hub stays disabled fail-closed without `CALVINO_CONFIRMATION_KEY`), the FR-7 cards emitted only from verified tool results (`payment_status`, `action_result`, `case_status`, and `action_confirmation` mapped from the parked approval payload), a per-turn decision trace on every `HubReply`, the deterministic `TemplateAgent` and the demo personas in `calvino.hub.sessions` (no free-form text until T-301, decision 10), and the Next.js customer screen replacing the minimal demo page: the card catalog with a named fallback for unknown keys, scenario buttons for UC-1 to UC-5, UC-7 and UC-8, confirm / deny buttons bound to the exact parked action, the operator's resume for a parked case, the glass-box panel reading only the selected turn's trace, and the ES / PT chrome toggle.

### Changed

- The agent-role LLM provider is Hetzner's Inference API and the judge stays on a second provider (decision 28, refining 20); DESIGN, ROADMAP, PLAN and the backlog name the `CALVINO_LLM_*` and `CALVINO_JUDGE_*` variables, and using a chat API as the System One classifier is recorded as rejected.
- The inference layout is recorded rather than left to be re-litigated: `calvino.llm/` is the external model boundary and Laya stays in `calvino.classifiers/`, because inference splits on whether the output is an input to the policy or downstream of it. A bare root module and a single all-inference folder are recorded as rejected alternatives.
- The language models are selected (decision 29): `Qwen/Qwen3.6-35B-A3B-FP8` for the agent on Hetzner and the dated release `deepseek/deepseek-v4-pro-0813` for the judge on OpenRouter. The judge id names an exact release; Hetzner's catalogue carries no version, so the agent's pin is a provider id and is recorded as one. The agent model stays open to the T-106 A/B.
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
