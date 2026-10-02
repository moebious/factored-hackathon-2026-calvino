# Project Calvino: Roadmap

How Calvino gets built: in waves of parallel work, each piece one branch, one worktree and one pull request. The product design is in [DESIGN.md](DESIGN.md); phases, tiers and their gates are in [PLAN.md](PLAN.md); the rules every contributor and coding agent follows are in [AGENTS.md](../AGENTS.md).

## Working principles

1. **Spec first.** Each stream has a technical specification before work starts; later waves get theirs just before they begin.
2. **One session = one PR = one topic.** Every unit of work has a branch, a "done when" and tests. Work that does not end in a mergeable PR is not started.
3. **Synthetic fixtures first.** Engineering that doesn't need the real data starts immediately, against small, labelled synthetic fixtures.
4. **Limited parallelism.** Four or five streams at a time. The maintainer approves every push and merges every PR, so more parallel streams than can be reviewed only creates a queue.
5. **Shared interfaces before parallel work.** The scaffolding PR (A0) merges first and fixes the package layout, the decision-record schema and the test setup that every other stream builds on.
6. **Gates, not dates.** A wave starts when the work it depends on is merged; a tier starts when the previous one is merged, deployed and evaluated.

## Prerequisites (maintainer)

- [ ] Merge the foundation PRs (scaffolding, git workflow enforcement, concept).
- [ ] Environment variables for agent sessions: dataset access (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`, `CALVINO_DATA_BUCKET`), the LLM provider key, `HF_TOKEN`.
- [ ] Hugging Face Space and Vercel project created; DNS for `calvino.rubrica.dev` when the app is ready.

## Wave 0: foundations without real data

Each stream is specified in a technical specification in [specs/](specs/README.md). A work session starts with one line: *"Implement `docs/specs/TSD-NNN-….md`, following AGENTS.md."*

| Stream | Branch | Builds | Done when |
|---|---|---|---|
| **A0. Scaffolding** (first, small) · [TSD-000](specs/TSD-000-scaffolding.md) | `build/python-scaffold` | `pyproject.toml`, `src/calvino/` package, pytest, ruff, CI test job, decision-record schema | CI runs lint and tests on an empty-but-real package |
| **A. Policy engine** · [TSD-001](specs/TSD-001-policy-engine.md) | `feat/policy-engine` | hard rules, two-threshold verdicts, out-of-scope outcome, decision log writer | fully unit-tested, no model calls; same inputs give the same verdict |
| **B. MCP tools** · [TSD-002](specs/TSD-002-mcp-tools.md) | `feat/mcp-tools` | MCP server, ISO 20022-aligned tool contracts, ownership and scope checks, idempotent write tools, adapter conformance suite, dataset adapter on a fixture | conformance and unauthorized-access tests pass |
| **C. Deployment skeleton** · [TSD-003](specs/TSD-003-deployment.md) | `build/deploy-skeleton` | Hugging Face Space container (Laya preloaded, weights baked in), Vercel app with `/api` rewrite and warm-up screen, keep-alive workflow | runs locally end to end; deploy steps documented for the maintainer |
| **D. Verifier framework** · [TSD-004](specs/TSD-004-verifier.md) | `feat/verifier` | rubric format, code checks, batched-judge interface with a mock model, fixed aggregation rule | rubric tests pass with mocked verdicts |
| **E. Laya service and calibration** · [TSD-005](specs/TSD-005-laya-service.md) | `feat/laya-service` | Laya client (multilingual pinned, neutral-key choices), temperature scaling, ECE / Brier / reliability plot | works end to end on a synthetic labelled set |

## Wave 1: data

Needs dataset access.

| Stream | Branch | Builds | Done when |
|---|---|---|---|
| **F. Contact-reason analysis** · [TSD-006](specs/TSD-006-contact-reason-analysis.md) | `eval/contact-reasons` | demand, first-contact resolution, escalation and handle time by reason, country and segment; complaint analysis; charts | the maintainer chooses the workflow, recorded in DECISIONS.md |
| **G. Contracts and quality report** | `data/contracts` | raw and clean contracts, validator, quality report, lineage | report generated on the cleaned layer |
| **H. Labels and splits** | `data/labels-splits` | labels, splits by customer and by time, gold-set rubric and first labels, freshness fixture | splits documented; leakage tests pass |

## Wave 2: classifiers, hub and customer app

Needs F and H (I, J) or Wave 0 (K, L).

| Stream | Branch | Builds |
|---|---|---|
| **I. Classifier evaluation** | `eval/classifiers` | majority, rules, logistic regression, Laya zero-shot and calibrated; thresholds by expected cost; calibration per language. In parallel, the maintainer runs Laya fine-tuning on Kaggle |
| **J. Portuguese test set** | `data/pt-test-set` | translated held-out cases and cases written in Portuguese, labelled synthetic |
| **K. Calvino hub** | `feat/hub` | LangGraph hub wiring A, B, D and E: identity → hard rules → decision classifier → Gate → verification → case file, with a human interrupt |
| **L. Customer app** | `feat/customer-app` | Laya card catalog (6–8 cards), clarification chips, glass box, scenario buttons, ES / PT toggle |

## Wave 3: end-to-end core (Tier 0)

| Stream | Branch | Builds |
|---|---|---|
| **M. Support agent and company brain** | `feat/support-agent` | Deep Agents worker for the chosen workflow; policy retrieval |
| **N. Handoff queue and audit timeline** | `feat/console-queue` | operator view of cases, approvals, timeline with the rule named on every refusal |
| **O. Evaluation harness** | `eval/end-to-end` | the brief's outcome metrics, adversarial cases, repeated runs, judge validation, error analysis |

**Gate:** deployed at `calvino.rubrica.dev`, results in the README. Tag `v0.4.0`.

## Wave 4: depth (Tier 1)

One stream each: durable cases (pause, restart, resume with approval) · risk-tiered verifier panel · coworker agent · analytics tab · fairness and counterfactual tests · second MCP adapter and the swap demo · one offline flywheel turn · console policy page with rule-and-replay.

## Wave 5: submission

Maintainer: slides, video pitch, submission email. Streams: README usage with real output, results report, release notes. Tag `v1.0.0`. Tier 2 (AG-UI / CopilotKit console, live verifier streaming, verifier lab) only with room to spare.

## After the hackathon

- **Methodology:** write up Calvino (Systems 1 → 3, hub and spoke, the governed flywheel).
- **Verification as a product:** the mixture of financial verifiers, offered to check any agent's work.
- **Real integrations:** a bank-core adapter, ISO 20022 XML validation, AG-UI so Calvino plugs into CopilotKit and OpenBot.
- **More workflows and channels:** messaging, voice, credit with a separate eligibility policy service.
- **Production:** the documented AWS VPC reference built out, a managed append-only audit store, an enterprise identity provider.
