# Project Calvino: Roadmap

How Calvino gets built: in waves of parallel work, each piece one branch, one worktree and one pull request. The product design is in [DESIGN.md](DESIGN.md); phases, tiers and their gates are in [PLAN.md](PLAN.md); the rules every contributor and coding agent follows are in [AGENTS.md](../AGENTS.md).

**Owners:** every task is owned by the maintainer (the data analyst has left the project); the backlog in [tasks/README.md](tasks/README.md) is the source of truth.

## Working principles

1. **Spec first.** Each stream has a technical specification before work starts; later waves get theirs just before they begin.
2. **One session = one PR = one topic.** Every unit of work has a branch, a "done when" and tests. Work that does not end in a mergeable PR is not started.
3. **Synthetic fixtures first.** Engineering that doesn't need the real data starts immediately, against small, labelled synthetic fixtures.
4. **Limited parallelism.** Four or five streams at a time. The maintainer approves every push and merges every PR, so more parallel streams than can be reviewed only creates a queue.
5. **Shared interfaces before parallel work.** The scaffolding PR (A0) merges first and fixes the package layout, the decision-record schema and the test setup that every other stream builds on.
6. **Gates, not dates.** A wave starts when the work it depends on is merged; a tier starts when the previous one is merged, deployed and evaluated.

## Prerequisites (maintainer)

- [x] Merge the foundation PRs (git workflow enforcement, concept, `v0.1.0`) and the Python scaffold (TSD-000).
- [ ] Environment variables for agent sessions: dataset access (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`, `CALVINO_DATA_BUCKET`), the LLM provider key, `HF_TOKEN`.
- [ ] Language-model variables (decisions 28 and 29): `CALVINO_LLM_API_KEY` with `CALVINO_LLM_MODEL=Qwen/Qwen3.6-35B-A3B-FP8` for the agent role on Hetzner, and `CALVINO_JUDGE_API_KEY`, `CALVINO_JUDGE_BASE_URL=https://openrouter.ai/api/v1` and `CALVINO_JUDGE_MODEL=deepseek/deepseek-v4-pro-0813` for the judge. `CALVINO_LLM_BASE_URL`, `CALVINO_LLM_MAX_REQUESTS` and `CALVINO_LLM_TIMEOUT_SECONDS` are optional overrides; nothing has a default that would send traffic somewhere nobody chose.
- [ ] Hugging Face Space and Vercel project created; DNS for `calvino.rubrica.dev` when the app is ready.
- [ ] Judge provider (decision 29): an OpenRouter account with credits and a spending cap, serving `deepseek/deepseek-v4-pro-0813` for the judge. The agent needs no paid provider, Hetzner serves that one. `HF_TOKEN` is still set for the Space, and `CALVINO_CONFIRMATION_KEY` for the tools.

## Wave 0: foundations without real data

Each stream is specified in a technical specification in [specs/](specs/README.md). A work session starts with one line: *"Implement `docs/specs/TSD-NNN-….md`, following AGENTS.md."*

| Stream | Branch | Builds | Done when |
|---|---|---|---|
| **A0. Scaffolding** (done) · [TSD-000](specs/TSD-000-scaffolding.md) | `build/python-scaffold` | `pyproject.toml`, `src/calvino/` package, pytest, ruff, CI test job, decision-record schema | CI runs lint and tests on an empty-but-real package |
| **A. Policy engine** · [TSD-001](specs/TSD-001-policy-engine.md) | `feat/policy-engine` | hard rules, two-threshold verdicts with the clarify band, out-of-scope outcome, Gate verdicts for cancel, retry and open investigation, per-currency limits | fully unit-tested, no model calls; same inputs give the same verdict |
| **B. MCP tools** · [TSD-002](specs/TSD-002-mcp-tools.md) | `feat/mcp-tools` | MCP server, ISO 20022-aligned tool contracts (camt.053/054, pacs.002, camt.027/029/056), the stuck-payments tools, ownership and eligibility checks, idempotent simulated writes, adapter conformance suite, dataset adapter on a fixture | conformance and unauthorized-access tests pass |
| **C. Deployment skeleton** · [TSD-003](specs/TSD-003-deployment.md) | `build/deploy-skeleton` | Hugging Face Space container (Laya preloaded, weights baked in, persistent storage for checkpoints and the decision log), Vercel app with `/api` rewrite and warm-up screen, keep-alive workflow | runs locally end to end; deploy steps documented for the maintainer |
| **D. Verifier framework** · [TSD-004](specs/TSD-004-verifier.md) | `feat/verifier` | rubric format with the stuck-payments criteria, code checks, batched-judge interface with a mock model, fixed aggregation rule, per-criterion checker recorded for the false-pass measurement | rubric tests pass with mocked verdicts |
| **E. Laya service and calibration** · [TSD-005](specs/TSD-005-laya-service.md) | `feat/laya-service` | Laya client (multilingual pinned, neutral-key choices) with the question set in DESIGN 6.1, temperature scaling, ECE / Brier / reliability plot | works end to end on a synthetic labelled set |

## Wave 1: data

Needs dataset access.

| Stream | Branch | Builds | Done when |
|---|---|---|---|
| **F. Workflow decision** (done) | — | full-data verification and chance tests; decision 17 (TSD-006 superseded) | recorded in DECISIONS.md |
| **G. Contracts, quality report and baseline** | `data/contracts`, `eval/baseline` | the analyst's full-data pipeline and validator, the data-quality report, the human baseline (T-104) with an independent cross-check | report and baseline generated on the full data |
| **H. Labels, splits and message set** | `data/labels-splits`, `data/message-set` | labels and gold-set rubric (T-103); seeded test cases with oracle outcomes and generated Spanish messages (T-106); freshness fixture | every test case has a seed record and an oracle outcome; leakage tests pass |

## Wave 2: classifiers, hub and customer app

Needs H (I, J) or Wave 0 (K, L).

| Stream | Branch | Builds |
|---|---|---|
| **I. Classifier evaluation** | `eval/classifiers` | majority, rules, logistic regression, Laya zero-shot and calibrated; thresholds by expected cost; calibration per language and dialect (fine-tuning is Tier 1) |
| **J. Portuguese test set** | `data/pt-test-set` | translated held-out messages and cases written in Portuguese, seeded like the Spanish set, local currencies only, labelled synthetic |
| **K. Calvino hub** | `feat/hub` | LangGraph hub wiring A, B, D and E through the five stages of decision 17: explain, clarify, act under the Gate, investigate (human interrupt, case file), follow up (resume) |
| **L. Customer app** | `feat/customer-app` | the 8-card catalog in PRD FR-7, problem-payment picker, glass box, scenario buttons, ES / PT toggle |

## Wave 3: end-to-end core (Tier 0)

| Stream | Branch | Builds |
|---|---|---|
| **M. Support agent** | `feat/support-agent` | Deep Agents worker for the explain, clarify, act and follow-up stages |
| **N. Handoff queue and audit timeline** | `feat/console-queue` | operator view of approvals and investigations, timeline with the rule named on every refusal |
| **O. Evaluation harness** | `eval/end-to-end` | the brief's outcome metrics scored against the seeded oracle, both baselines, the bare-LLM ablation, the verifier's false-pass rate, repeated runs, error analysis |
| **P. Durable cases** | `feat/durable-cases` | a case survives a restart and resumes (T-401) |
| **Q. Policy replay** | `feat/policy-replay` | replay the log under a new policy version (T-408) |
| **R. One flywheel turn** | `eval/flywheel` | recalibration from operator labels, measured on the frozen set (T-407) |

**Gate:** deployed at `calvino.rubrica.dev`, results in the README. Tag `v0.4.0`.

## Wave 4: depth (Tier 1)

One stream each: Laya fine-tuning · risk-tiered verifier panel · coworker agent · analytics tab · counterfactual fairness tests · second MCP adapter and the swap demo.

## Wave 5: submission

Maintainer: slides, video pitch, submission email. Streams: README usage with real output, results report, release notes. Tag `v1.0.0`. Tier 2 (AG-UI / CopilotKit console, live verifier streaming, verifier lab) only with room to spare.

## After the hackathon

- **Methodology:** write up Calvino (Systems 1 → 3, hub and spoke, the governed flywheel).
- **Verification as a product:** the mixture of financial verifiers, offered to check any agent's work.
- **Real integrations:** a bank-core adapter, ISO 20022 XML validation, AG-UI so Calvino plugs into CopilotKit and OpenBot.
- **More workflows and channels:** messaging, voice, credit with a separate eligibility policy service.
- **Production:** the documented AWS VPC reference built out, a managed append-only audit store, an enterprise identity provider.
