# Project Calvino: Roadmap

How Calvino gets built: in waves of parallel work, each piece one branch, one worktree and one pull request. The product design is in [DESIGN.md](DESIGN.md); phases, thesis evidence and gates are in [PLAN.md](PLAN.md); the rules every contributor and coding agent follows are in [AGENTS.md](../AGENTS.md). Decisions 34–37 reclassify some original Tier 1/2 ideas as **core experiments**, without claiming that they have already run.

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
- [ ] Decide a public host for the **full** hub and Next.js app, create the accounts and validate the deployed journey; DNS for `calvino.rubrica.dev` when ready. T-305's decision-only Gradio fallback cannot complete T-304.
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
| **G. Contracts, quality report and baseline** | `data/contracts`, `eval/baseline` | T-102 and the full-data inventory are merged; T-104 completes the category-level human baseline, without pretending a call can be matched to its transaction | report and baseline reproducible on the full data with counts and denominators |
| **H. Labels, splits, corrections and message set** | `data/labels-splits`, `data/message-set`, `data/freshness-fixture` | T-103's rubric/splits exist and its first-50 sheet is being hand-labelled; T-106 builds disjoint train/calibration/test messages using the existing T-303 oracle definitions; T-105 proves late/corrected records invalidate affected labels and promotion evidence | leakage rules pass, corrected lineage is explicit and the frozen T-303 suite never trains a model |

## Wave 2: specialised System 1 and the grounded journey

The hub and customer app (K, L) are already merged. Training depends on H; the production-shaped dataset adapter can proceed independently.

| Stream | Branch | Builds |
|---|---|---|
| **I. Laya fine-tuning and classifier evaluation** | `eval/laya-finetune`, `eval/classifiers` | T-202 trains open-weight Laya on reviewed, disjoint banking messages; T-201 compares majority, rules, logistic regression, base, calibrated and fine-tuned/calibrated Laya on one untouched held-out set, then justifies versioned thresholds |
| **J. Portuguese test set** | `data/pt-test-set` | translated held-out messages and cases written in Portuguese, seeded like the Spanish set, local currencies only, labelled synthetic |
| **K. Calvino hub** | `feat/hub` | LangGraph hub wiring A, B, D and E through the five stages of decision 17: explain, clarify, act under the Gate, investigate (human interrupt, case file), follow up (resume) |
| **L. Customer app** | `feat/customer-app` | the 8-card catalog in PRD FR-7, problem-payment picker, glass box, scenario buttons, ES / PT toggle |
| **M. Cleaned-table adapter** | `feat/workflow-tools` | T-206 backs the existing tools with the full cleaned tables and source mappings; no fabricated call-to-transaction relationship |

## Wave 3: end-to-end product and thesis proof

These are **separate experiments** over one governed workflow. A documented proposal or skipped keyed run is not a measured result. Run the core offline tests even when the hosting accounts are blocked, but do not claim a deployed product until T-304 passes live.

| Stream | Branch | Builds and proves |
|---|---|---|
| **N. Bounded support agent** | `feat/support-agent` | T-301 writes grounded ES/PT replies using stage-scoped tools and policy retrieval; the model cannot authorize writes |
| **O. Human workspace and durable resume** | `feat/console-queue`, `feat/durable-cases` | T-302 gives operators verified dossiers, attributable reply/notes edits, approvals and takeover without bypassing blocks; T-401 resumes a parked turn by case ref after restart |
| **P. Evaluation and verifier lab** | `eval/end-to-end`, `eval/verifier-lab` | T-303 measures safe outcomes, errors, bare-LLM ablation and judge false passes on reviewed labels; T-603 tests human-authored rubric changes against development and frozen promotion sets |
| **Q. Risk-tiered veto and language evidence** | `feat/verifier-panel`, `eval/fairness` | T-402 compares a **pre-execution, veto-only** specialist panel against the current cascade on the same high-risk cases; T-405 reports paired model differences separately from documented policy-driven ES/PT outcome changes |
| **R. Replay and governed learning** | `feat/policy-replay`, `eval/flywheel` | T-408 writes a policy-version verdict-delta/safety scorecard; T-407 runs one offline corrected-data-to-reviewed-label-to-candidate-to-human-sign-off loop, including a rejected candidate if warranted |
| **S. Bank boundary** | `feat/second-adapter`, `feat/iso20022-xml` | T-406 swaps two synthetic internal formats without changing the hub/policy; T-604 validates one authorized action through mock ISO 20022 middleware and verifies its response, with no general compliance claim |
| **T. Public product** | `build/deploy-demo` | T-304 serves the full hub/customer app and passes a live cold-start, scenario and restart check; T-305 is an explicitly limited emergency diagnostic fallback |

**Gate:** the public full journey works; claims for each experiment link to actual counts, model/policy/rubric versions and limitations in the README. An offline experiment cannot stand in for a live pre-execution shield, and zero detected unsafe cases does not establish zero risk.

## Optional depth after the core gate

Additional risk tiers, bank profiles, ISO message types, case-management features and larger group studies are optional. T-403 (coworker) and T-404 (interactive analytics tab) are **future** product surfaces; the current queue and reproducible reports carry the evidence without them.

## Wave 5: submission

Maintainer: slides, video pitch, submission email. T-501 puts measured results and named gaps in the README; T-502 is final changelog/tag hygiene, not a backfilled release programme. T-601 (AG-UI/CopilotKit) and T-602 (live verifier streaming) remain future UI integrations, not core safety evidence.

## After the hackathon

- **Methodology:** write up Calvino (Systems 1 → 3, hub and spoke, the governed flywheel).
- **Verification as a product:** extend the measured financial verifier benchmark to other regulated workflows only after its false-pass properties hold on reviewed labels.
- **Real integrations:** bank-specific authentication, profile and reconciliation work beyond the mock ISO 20022 message and adapter swap; AG-UI may later plug Calvino into another agent workspace.
- **More workflows and channels:** messaging, voice, credit with a separate eligibility policy service.
- **Production:** the documented AWS VPC reference built out, a managed append-only audit store, an enterprise identity provider.
