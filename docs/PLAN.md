# Project Calvino: Build Plan

Internal plan for the hackathon build. Requirements are in [BRD.md](BRD.md) and [PRD.md](PRD.md), the design in [DESIGN.md](DESIGN.md), build specifications in [specs/](specs/README.md); how the work is split into parallel streams is in [ROADMAP.md](ROADMAP.md).

## Phases

Phases run in order; each one ends with its pull requests merged and, where listed, a version tag on `main`.

| # | Goal | Done when | Branch types | Version |
|---|---|---|---|---|
| 1 | **Foundation**: design, decisions, repository standards and git workflow | scaffolding and enforcement PRs merged | `docs/`, `ci/` | `v0.1.0` |
| 2 | **Data**: pipeline with contracts and quality checks, the data-quality report, the human baseline, labels, splits and the seeded message set | quality report and baseline on the full data; every test case has a seed record and an oracle outcome; leakage-free splits exist | `data/`, `eval/` | `v0.2.0` |
| 3 | **Classifiers, policy and tools**: Laya base, calibrated and fine-tuned vs baselines; Portuguese test set; policy engine with unit tests; MCP server with the dataset adapter, ISO 20022-aligned contracts and conformance tests | fine-tuned and baseline classifier results reported on the same held-out data, including Portuguese evaluation; policy and tool permission checks fully unit tested | `feat/`, `eval/`, `data/` | `v0.3.0` |
| 4 | **Hub and deployment**: Calvino hub (decision classifier, Gate, verifier cascade, human interrupt), support chat agent; customer app with Laya cards and glass box; handoff queue; deployed at `calvino.rubrica.dev` | normal, ambiguous, unsupported and human-handoff paths run end to end on the deployed link, in Spanish and Portuguese; keep-alive, baked weights and a warm-up screen in place | `feat/`, `build/` | `v0.4.0` |
| 5 | **Evaluation and governed evolution**: evaluation including failure cases; offline verifier lab, risk-tiered pre-execution veto comparison, paired fairness evidence, one reviewed flywheel turn and policy replay; reproducible metrics and README usage | metrics from the brief and the thesis experiments reported with sample sizes, limitations and explicit non-results | `eval/`, `docs/` | `v0.5.0` |
| 6 | **Submission**: slides, video pitch, final checks, email submission | all four deliverables sent | `docs/`, `fix/` | `v1.0.0` |

A deployed, working link is a required deliverable, so phase 4 includes the customer app and the deployment.

### Phase 2 in detail

Small PRs, in this order of priority if time runs short:

1. ~~Contact-reason analysis and workflow decision~~: done (decision 17; DATA.md findings).
2. `eval/baseline`: the maintainer's reproducible, full-data category-level human baseline, checked against the independent headline cross-check.
3. `data/contracts`: raw and clean contracts, validator, the data-quality report, lineage (the analyst's pipeline).
4. `data/labels-splits`: labels, splits by customer and by time, leakage rules, the labelling rubric and the first ~50 gold labels.
5. `data/message-set`: leakage-separated generated messages for training, calibration and test (T-106), reusing T-303's oracle definitions but not training on its frozen 50-case suite.
6. `data/freshness-fixture`: corrected-record lineage through labels and promotion evidence (T-105).

Tables in use: `transactions`, `complaints`, `call_center_interactions`, `customers`, `products`, `daily_exchange_rates` (and `satisfaction_surveys` if CSAT enters the baseline). `call_transcripts` is used only for the data-quality finding (decision 16). The analyst's Parquet lakehouse is the clean layer.

## Ladder

Each tier starts only when the one before it is merged, deployed and evaluated.

| Tier | Contents | Gate to move up |
|---|---|---|
| **0: Thesis proof and submittable core** | the five-stage journey, Laya fine-tuning and held-out comparison, one offline governed flywheel turn, deterministic policy replay and promotion report, the verifier cascade and its false-pass measurement, an offline comparison of a risk-tiered pre-execution veto, paired language/dialect evidence, operator workspace and restart-safe parked turns, two synthetic adapters and one mock ISO 20022 action exchange, a deployed full app and a bare-LLM ablation | the claim attached to each result is actually measured; all four deliverables could be sent as they are |
| **1: Optional depth** | a wider risk panel, larger dataset and group slices, additional ISO operations and bank profiles, more complete operational case management | core evaluated, numbers in the README |
| **2: Future integrations** | AG-UI / CopilotKit, live verifier streaming, coworker agent, interactive analytics tab and real bank-core connection | only when a real integration or measured user need warrants it |
| **3: Documented only** | A2A, more verticals and bank cores, enterprise identity provider, data residency, OpenDots-style channels | stays documentation |

## Cut order and protected measurements

If time runs short before submission, cut in this order, one item at a time, and record each cut in the README's remaining-work list:

1. Extra UI polish beyond the fixed cards, operator workspace and glass box.
2. Additional ISO message types and specialist checks beyond the one measured operation.
3. A larger Portuguese/counterfactual or adapter-swap case set, **not** the paired and conformance evidence itself.
4. The follow-up reply (UC-8), while retaining restart-safe case resume and an honest remaining-work note.

**Never cut the investigate stage:** humans already resolve 91.5% of Transaccional calls on first contact `[measured]`, so investigations are where Calvino's improvement story sits (DATA.md, decision 17).

**Do not silently cut the thesis proof:** fine-tuned Laya versus baselines (T-202/T-201), the reviewed offline flywheel (T-407), policy-version verdict deltas and safety gate (T-408), the pre-execution panel comparison (T-402), paired fairness evidence (T-405), adapter swap (T-406) and one verified mock ISO bank action (T-604) are the accepted experiments of decisions 34–37. If one cannot run, report it as `not run` and narrow the corresponding pitch claim; no illustrative threshold, latency, cost, fairness gap or false-pass rate is a measured result.

**Never cut** these three measurements: together they turn "safe automation" from a claim into evidence, and a demo without them scores far lower than a plainer demo with them.

- **Unsafe outcomes** on the seeded oracle test set, with counts and denominators.
- **The bare-LLM ablation:** the same adversarial cases with and without the harness.
- **The verifier's false-pass rate** against hand labels.

**Checkpoint:** if the hub cannot run explain, clarify, act and investigate end to end on the public link, apply the cut order and document what actually runs. A decision-only fallback must not be presented as the full product.

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
| Laya zero-shot quality on ES/PT | core fine-tuning and held-out comparison against calibrated base Laya and logistic regression; Portuguese remains test-only |
| No GPU in the dev container | report CPU latency honestly; fine-tune on Kaggle if Tier 1 is reached |
| Synthetic labels too easy or noisy; team-generated text too easy (decision 16) | separate generation prompts for train and test, adversarial rewordings, a hand-written subset, time split, gold set |
| Scope creep | the ladder and its gates; one workflow, built in depth |
| Demo link asleep or slow during judging | keep-alive ping, weights baked into the image, warm-up screen; UI on Vercel always loads |
| Public link spends LLM credits | spending cap on the key, rate limit |

## Blockers and open decisions

- [x] Workflow choice: stuck payments, end to end (decision 17)
- [ ] Full public hosting: decision 10's Vercel + Space path is designed, but the account and budget path must be validated; decision 27's free Gradio fallback serves only the decision demo
- [ ] DNS record for `calvino.rubrica.dev` (maintainer, when the app is ready)
- [ ] LLM keys: a Hetzner token and the agent model id, plus the judge's provider key (decision 28; maintainer)
- [ ] Hugging Face Space and Vercel accounts, `HF_TOKEN` (maintainer)
- [ ] Laya fine-tuning on a GPU (Kaggle): part of the core thesis comparison (T-202/T-201)
