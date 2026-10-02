# Project Calvino: Build Plan

Internal plan for the hackathon build. Requirements are in [BRD.md](BRD.md) and [PRD.md](PRD.md), the design in [DESIGN.md](DESIGN.md), build specifications in [specs/](specs/README.md); how the work is split into parallel streams is in [ROADMAP.md](ROADMAP.md).

## Phases

Phases run in order; each one ends with its pull requests merged and, where listed, a version tag on `main`.

| # | Goal | Done when | Branch types | Version |
|---|---|---|---|---|
| 1 | **Foundation**: design, decisions, repository standards and git workflow | scaffolding and enforcement PRs merged | `docs/`, `ci/` | `v0.1.0` |
| 2 | **Data**: pipeline with contracts and quality checks, contact-reason analysis, workflow choice, labels and splits | the workflow is chosen from the data and labelled, leakage-free splits exist | `data/` | `v0.2.0` |
| 3 | **Classifiers, policy and tools**: Laya zero-shot, calibrated (and fine-tuned, if pursued) vs baselines; Portuguese test set; policy engine with unit tests; MCP server with the dataset adapter, ISO 20022-aligned contracts and conformance tests | classifier results reported on held-out data, including Portuguese; policy and tool permission checks fully unit tested | `feat/`, `eval/`, `data/` | `v0.3.0` |
| 4 | **Hub and deployment**: Calvino hub (decision classifier, Gate, verifier cascade, human interrupt), support chat agent; customer app with Laya cards and glass box; handoff queue; deployed at `calvino.rubrica.dev` | normal, ambiguous, unsupported and human-handoff paths run end to end on the deployed link, in Spanish and Portuguese; keep-alive, baked weights and a warm-up screen in place | `feat/`, `build/` | `v0.4.0` |
| 5 | **Evaluation and analytics**: evaluation run including failure cases; metrics and visualizations for decision support; README usage | metrics from the brief reported with sample sizes and limitations | `eval/`, `docs/` | `v0.5.0` |
| 6 | **Submission**: slides, video pitch, final checks, email submission | all four deliverables sent | `docs/`, `fix/` | `v1.0.0` |

A deployed, working link is a required deliverable, so phase 4 includes the customer app and the deployment.

### Phase 2 in detail

Small PRs, in this order of priority if time runs short:

1. `eval/contact-reasons`: contact-reason analysis (volume, first-contact resolution, escalation, handle time, by country, channel and segment) and complaint analysis. Produces the charts reused in the slides and analytics.
2. **Workflow decision**, recorded in DECISIONS.md.
3. `data/labels-splits`: labels, splits by customer and by time, leakage rules, the labelling rubric and the first ~50 gold labels.
4. `data/contracts`: raw and clean contracts for the tables in use, validator, quality report, lineage.
5. `eval/baseline`: the human baseline for the chosen workflow.
6. `data/freshness-fixture`: the labelled update-correctness fixture.

Tables in use: `call_center_interactions`, `call_transcripts`, `complaints`, `customers`, `transactions`, `products` (and `satisfaction_surveys` if CSAT enters the baseline). The cleaned parquet is the clean layer; it is not redone.

## Ladder

Each tier starts only when the one before it is merged, deployed and evaluated.

| Tier | Contents | Gate to move up |
|---|---|---|
| **0: Submittable core** | everything in phases 2–5 above, with the verifier cascade (one batched judge) and the operator handoff queue with the audit timeline | all four deliverables could be sent as they are |
| **1: Depth** | durable cases (pause, restart, resume with approval); Laya fine-tuning; risk-tiered verifier panel; coworker agent; analytics tab; fairness and counterfactual tests; second MCP adapter; console policy page with rule-and-replay | core evaluated, numbers in the README |
| **2: Integration standards** | AG-UI endpoint and CopilotKit console; live verifier streaming; offline verifier lab; ISO 20022 XML validation | Tier 1 demoed on the deployed link |
| **3: Documented only** | A2A, more verticals and bank cores, enterprise identity provider, data residency, OpenDots-style channels | stays documentation |

## Submission deliverables

From the [hackathon page](https://www.factored.ai/careers/ai-data-hackathon), sent by email to the organizers:

| Deliverable | Requirement | Phase |
|---|---|---|
| Public GitHub repository | named `factored-hackathon-2026-[team-name]` | done |
| Deployed solution | a working link to the tool | 4 |
| Presentation | 4–6 slides: approach, results, technical decisions | 6 |
| Video pitch | 3 minutes or less: working solution and core architectural choices | 6 |

Judging dimensions: technical judgment, AI engineering, data engineering, machine learning and data analytics ("quality over quantity"). Spanish and Portuguese demonstrations are required.

## Risks

| Risk | Mitigation |
|---|---|
| Laya zero-shot quality on ES/PT | calibration + fine-tuning; logistic-regression fallback |
| No GPU in the dev container | fine-tune on Kaggle; report CPU latency honestly |
| Synthetic labels too easy or noisy | text-only features, time split, adversarial rewordings, gold set |
| Scope creep | the ladder and its gates; one workflow, built in depth |
| Demo link asleep or slow during judging | keep-alive ping, weights baked into the image, warm-up screen; UI on Vercel always loads |
| Public link spends LLM credits | spending cap on the key, demo passcode, rate limit |

## Blockers and open decisions

- [ ] Workflow choice (made in phase 2, from the data)
- [x] Hosting: Vercel (UI) + Hugging Face Space (backend) at `calvino.rubrica.dev` (decision #10)
- [ ] DNS record for `calvino.rubrica.dev` (maintainer, when the app is ready)
- [ ] LLM provider and API key (needed in phase 4; maintainer, in progress)
- [ ] Laya fine-tuning on a GPU (Kaggle), if pursued in phase 3
