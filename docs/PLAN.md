# Project Calvino: Build Plan

Internal plan for the hackathon build. Requirements are in [BRD.md](BRD.md) and [PRD.md](PRD.md), the design in [DESIGN.md](DESIGN.md), build specifications in [specs/](specs/README.md); how the work is split into parallel streams is in [ROADMAP.md](ROADMAP.md).

## Phases

Phases run in order; each one ends with its pull requests merged and, where listed, a version tag on `main`.

| # | Goal | Done when | Branch types | Version |
|---|---|---|---|---|
| 1 | **Foundation**: design, decisions, repository standards and git workflow | scaffolding and enforcement PRs merged | `docs/`, `ci/` | `v0.1.0` |
| 2 | **Data**: pipeline with contracts and quality checks, the data-quality report, the human baseline, labels, splits and the seeded message set | quality report and baseline on the full data; every test case has a seed record and an oracle outcome; leakage-free splits exist | `data/`, `eval/` | `v0.2.0` |
| 3 | **Classifiers, policy and tools**: Laya zero-shot and calibrated vs baselines (fine-tuning is Tier 1); Portuguese test set; policy engine with unit tests; MCP server with the dataset adapter, ISO 20022-aligned contracts and conformance tests | classifier results reported on held-out data, including Portuguese; policy and tool permission checks fully unit tested | `feat/`, `eval/`, `data/` | `v0.3.0` |
| 4 | **Hub and deployment**: Calvino hub (decision classifier, Gate, verifier cascade, human interrupt), support chat agent; customer app with Laya cards and glass box; handoff queue; deployed at `calvino.rubrica.dev` | normal, ambiguous, unsupported and human-handoff paths run end to end on the deployed link, in Spanish and Portuguese; keep-alive, baked weights and a warm-up screen in place | `feat/`, `build/` | `v0.4.0` |
| 5 | **Evaluation and analytics**: evaluation run including failure cases; metrics and visualizations for decision support; README usage | metrics from the brief reported with sample sizes and limitations | `eval/`, `docs/` | `v0.5.0` |
| 6 | **Submission**: slides, video pitch, final checks, email submission | all four deliverables sent | `docs/`, `fix/` | `v1.0.0` |

A deployed, working link is a required deliverable, so phase 4 includes the customer app and the deployment.

### Phase 2 in detail

Small PRs, in this order of priority if time runs short:

1. ~~Contact-reason analysis and workflow decision~~: done (decision 17; DATA.md findings).
2. `eval/baseline`: the human baseline on the full data (the analyst), cross-checked by an analysis session.
3. `data/contracts`: raw and clean contracts, validator, the data-quality report, lineage (the analyst's pipeline).
4. `data/labels-splits`: labels, splits by customer and by time, leakage rules, the labelling rubric and the first ~50 gold labels.
5. `data/message-set`: seeded test cases with oracle outcomes and generated messages (T-106).
6. `data/freshness-fixture`: the labelled update-correctness fixture.

Tables in use: `transactions`, `complaints`, `call_center_interactions`, `customers`, `products`, `daily_exchange_rates` (and `satisfaction_surveys` if CSAT enters the baseline). `call_transcripts` is used only for the data-quality finding (decision 16). The analyst's Parquet lakehouse is the clean layer.

## Ladder

Each tier starts only when the one before it is merged, deployed and evaluated.

| Tier | Contents | Gate to move up |
|---|---|---|
| **0: Submittable core** | everything in phases 2–5 above, with the verifier cascade (one batched judge), the operator handoff queue with the audit timeline, and, for the stuck-payments workflow (decision 17): durable cases, policy replay, one offline flywheel turn and a bare-LLM ablation | all four deliverables could be sent as they are |
| **1: Depth** | Laya fine-tuning; risk-tiered verifier panel; coworker agent; analytics tab; counterfactual fairness tests; second MCP adapter | core evaluated, numbers in the README |
| **2: Integration standards** | AG-UI endpoint and CopilotKit console; live verifier streaming; offline verifier lab; ISO 20022 XML validation | Tier 1 demoed on the deployed link |
| **3: Documented only** | A2A, more verticals and bank cores, enterprise identity provider, data residency, OpenDots-style channels | stays documentation |

## Cut order and protected measurements

If time runs short before submission, cut in this order, one item at a time, and record each cut in the README's remaining-work list:

1. The flywheel turn (T-407).
2. Policy replay (T-408).
3. The follow-up stage (UC-8): the case resumes, but the "how is my case?" reply is not built.
4. UI polish beyond the card catalog and the glass box.

**Never cut the investigate stage:** humans already resolve 91.5% of Transaccional calls on first contact `[measured]`, so investigations are where Calvino's improvement story sits (DATA.md, decision 17).

**Never cut** these three measurements: together they turn "safe automation" from a claim into evidence, and a demo without them scores far lower than a plainer demo with them.

- **Unsafe outcomes** on the seeded oracle test set, with counts and denominators.
- **The bare-LLM ablation:** the same adversarial cases with and without the harness.
- **The verifier's false-pass rate** against hand labels.

**Checkpoint:** if the hub does not run the explain, clarify, act and investigate stages end to end by the end of the second-to-last working day, apply the cut order and switch the customer app to a minimal page so the deployed link still works.

**Score targets** from the audits: about 9 with all of Tier 0 and the three measurements; about 8 with the core stages and the measurements; about 6 for a working demo without them `[hypothesis]`.

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
| Laya zero-shot quality on ES/PT | calibration; logistic-regression fallback; fine-tuning in Tier 1 |
| No GPU in the dev container | report CPU latency honestly; fine-tune on Kaggle if Tier 1 is reached |
| Synthetic labels too easy or noisy; team-generated text too easy (decision 16) | separate generation prompts for train and test, adversarial rewordings, a hand-written subset, time split, gold set |
| Scope creep | the ladder and its gates; one workflow, built in depth |
| Demo link asleep or slow during judging | keep-alive ping, weights baked into the image, warm-up screen; UI on Vercel always loads |
| Public link spends LLM credits | spending cap on the key, demo passcode, rate limit |

## Blockers and open decisions

- [x] Workflow choice: stuck payments, end to end (decision 17)
- [x] Hosting: Vercel (UI) + Hugging Face Space (backend) at `calvino.rubrica.dev` (decision #10)
- [ ] DNS record for `calvino.rubrica.dev` (maintainer, when the app is ready)
- [ ] LLM provider and API key (needed in phase 4; maintainer, in progress)
- [ ] Hugging Face Space and Vercel accounts, `HF_TOKEN` (maintainer)
- [ ] Laya fine-tuning on a GPU (Kaggle): Tier 1 only
