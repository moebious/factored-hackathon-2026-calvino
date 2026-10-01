# Project Calvino: Build Plan

Internal plan for the hackathon build (deadline: Monday 2026-10-05). The product design lives in [DESIGN.md](DESIGN.md).

## Scope (4 days, solo)

| Tier | Contents |
|---|---|
| **Build and demo** | LangGraph harness (Router/Gate/Verifier + interrupts), Laya classifiers, policy engine, one MCP server for mock banking tools with auth, CopilotKit/AG-UI frontend with a few generative components, decision log, evaluation |
| **Build thin** | REST endpoint, evaluation/replay CLI, one vertical-pack config |
| **Design and document only** | A2A, extra verticals, enterprise identity provider, data residency |

## Risks

| Risk | Mitigation |
|---|---|
| Laya zero-shot quality on ES/PT | calibration + fine-tuning; logistic-regression fallback |
| No GPU in the dev container | fine-tune on Kaggle; report CPU latency honestly |
| Synthetic labels too easy or noisy | text-only features, time split, adversarial rewordings, gold set |
| Scope creep | tiers above; one workflow, built in depth |

## Blockers

- [ ] S3 access to the dataset (needed for labels and the workflow choice)
- [ ] Data contracts section
- [ ] Workflow choice
