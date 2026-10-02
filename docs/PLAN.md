# Project Calvino: Build Plan

Internal plan for the hackathon build. The product design lives in [DESIGN.md](DESIGN.md).

## Phases

Phases run in order; each one ends with its pull requests merged and, where listed, a version tag on `main`.

| # | Goal | Done when | Branch types | Version |
|---|---|---|---|---|
| 1 | **Foundation**: design, decisions, repository standards and git workflow | scaffolding and enforcement PRs merged | `docs/`, `ci/` | `v0.1.0` |
| 2 | **Data**: pipeline with contracts and quality checks, contact-reason analysis, workflow choice, labels and splits | the workflow is chosen from the data and labelled, leakage-free splits exist | `data/` | `v0.2.0` |
| 3 | **Classifiers and policy**: Laya zero-shot baseline, calibration and comparison against a baseline; policy engine with unit tests; mock banking tools with authentication | classifier results reported on held-out data; policy and tool permission checks fully unit tested | `feat/`, `eval/` | `v0.3.0` |
| 4 | **Harness and deployment**: LangGraph Router, Gate, Verifier and human interrupt; minimal UI; deployed at a public link; end-to-end demo in Spanish and Portuguese | normal, ambiguous and human-handoff paths run end to end on the deployed link | `feat/`, `build/` | `v0.4.0` |
| 5 | **Evaluation and analytics**: evaluation run including failure cases; metrics and visualizations for decision support; README usage | metrics from the brief reported with sample sizes and limitations | `eval/`, `docs/` | `v0.5.0` |
| 6 | **Submission**: slides, video pitch, final checks, email submission | all four deliverables sent | `docs/`, `fix/` | `v1.0.0` |

A deployed, working link is a required deliverable, so phase 4 includes a minimal UI (chat plus the decision trail) and a deployment. Richer generative UI only if time allows.

## Submission deliverables

From the [hackathon page](https://www.factored.ai/careers/ai-data-hackathon), sent by email to the organizers:

| Deliverable | Requirement | Phase |
|---|---|---|
| Public GitHub repository | named `factored-hackathon-2026-[team-name]` | done |
| Deployed solution | a working link to the tool | 4 |
| Presentation | 4–6 slides: approach, results, technical decisions | 6 |
| Video pitch | 3 minutes or less: working solution and core architectural choices | 6 |

Judging dimensions: technical judgment, AI engineering, data engineering, machine learning and data analytics ("quality over quantity"). Spanish and Portuguese demonstrations are required.

## Scope

| Tier | Contents |
|---|---|
| **Build and demo** | LangGraph harness (Router/Gate/Verifier + interrupts), Laya classifiers, policy engine, one MCP server for mock banking tools with auth, decision log, evaluation, minimal UI, deployment at a public link |
| **Build thin** | CopilotKit/AG-UI generative components, REST endpoint, evaluation/replay CLI, one vertical-pack config |
| **Design and document only** | A2A, extra verticals, enterprise identity provider, data residency |

## Risks

| Risk | Mitigation |
|---|---|
| Laya zero-shot quality on ES/PT | calibration + fine-tuning; logistic-regression fallback |
| No GPU in the dev container | fine-tune on Kaggle; report CPU latency honestly |
| Synthetic labels too easy or noisy | text-only features, time split, adversarial rewordings, gold set |
| Scope creep | tiers above; one workflow, built in depth |

## Blockers and open decisions

- [ ] Workflow choice (made in phase 2, from the data)
- [ ] Hosting target for the deployed link (needed in phase 4)
- [ ] LLM provider and API key (needed in phase 4; maintainer, in progress)
- [ ] Laya fine-tuning on a GPU (Kaggle), if pursued in phase 3
