# Tasks: backlog and orchestration

*Every piece of remaining work, with its dependencies, so new sessions can pick it up. Wave 0 tasks have full specifications; later tasks have task cards that are completed into a specification as their first step, once the facts they depend on (the workflow choice, the data) are known.*

## How work is picked up

1. **Choose a task** whose dependencies are merged and that isn't blocked (see the backlog). Prefer tasks marked parallel-safe when several sessions run at once.
2. **Start the session with one line:**
   - a task with a spec: *"Implement `docs/specs/TSD-NNN-….md`, following AGENTS.md."*
   - a task with a card: *"Take `docs/tasks/T-NNN-….md`, following AGENTS.md: write its specification first and wait for approval."*
3. **Judgment checkpoints** (marked in the backlog) need the strongest available model or the maintainer's review of the reasoning before committing.
4. **One task = one branch = one worktree = one pull request.** Commit locally; the maintainer approves every push.
5. **When a task is done,** update its status in this table and the current state in [HANDOFF.md](../HANDOFF.md) in the same pull request.

If GitHub Issues are used for tracking, create one issue per task with its ID in the title, a milestone per wave, and close it from the pull request ("Closes #n"). The files here stay the source of truth for the content.

## Rules for parallel sessions

- At most four or five sessions at a time; the maintainer reviews and merges every PR.
- Shared interfaces come first: TSD-000 merges before any other Wave 0 work.
- Sessions never edit the same file in parallel without coordinating through the maintainer; when two tasks must touch the same file (for example DECISIONS.md), the second rebases on the first.
- Stacked pull requests stay drafts until GitHub retargets them to `main`.

## Backlog

Status: `todo`, `spec` (specification written, awaiting approval), `doing`, `review` (PR open), `done`.

| ID | Task | Wave | Depends on | Blocked by | Model | Parallel | Status |
|---|---|---|---|---|---|---|---|
| [T-000](../specs/TSD-000-scaffolding.md) | Python scaffolding and shared types | 0 | docs PRs merged | — | standard | no (first) | review |
| [T-001](../specs/TSD-001-policy-engine.md) | Policy engine | 0 | T-000 | — | standard | yes | spec |
| [T-002](../specs/TSD-002-mcp-tools.md) | MCP tools and ISO 20022-aligned contracts | 0 | T-000 | — | standard | yes | spec |
| [T-003](../specs/TSD-003-deployment.md) | Deployment skeleton | 0 | T-000 | — | standard | yes | spec |
| [T-004](../specs/TSD-004-verifier.md) | Verifier framework | 0 | T-000 | — | standard | yes | spec |
| [T-005](../specs/TSD-005-laya-service.md) | Laya service and calibration | 0 | T-000 | — | standard | yes | spec |
| [T-101](T-101-contact-reason-analysis.md) | Contact-reason analysis and workflow decision | 1 | — | dataset access | judgment checkpoint | yes | done (decision 17) |
| [T-102](T-102-data-contracts.md) | Data contracts, quality report and lineage | 1 | T-000 | dataset access | standard | yes | todo |
| [T-103](T-103-labels-splits.md) | Labels, splits and gold-set rubric | 1 | T-101 | workflow decision | judgment checkpoint | no | todo |
| [T-104](T-104-human-baseline.md) | Human baseline for the chosen workflow | 1 | T-101 | workflow decision | standard | yes | todo |
| [T-105](T-105-freshness-fixture.md) | Update-correctness fixture | 1 | T-102 | — | standard | yes | todo |
| [T-106](T-106-message-set.md) | Team-generated customer message set | 1 | T-103 | LLM provider | standard + maintainer review | no | todo |
| [T-201](T-201-classifier-evaluation.md) | Classifier evaluation and thresholds | 2 | T-005, T-106 | — | judgment checkpoint | no | todo |
| [T-202](T-202-laya-fine-tuning.md) | Laya fine-tuning on Kaggle | Tier 1 | T-106 | GPU (maintainer runs the notebook) | standard | yes | todo |
| [T-203](T-203-portuguese-test-set.md) | Portuguese test set | 2 | T-106 | — | standard | yes | todo |
| [T-204](T-204-calvino-hub.md) | Calvino hub | 2 | T-001, T-002, T-004, T-005 | — | judgment checkpoint | no | todo |
| [T-205](T-205-customer-app.md) | Customer app with Laya cards | 2 | T-003 | — | standard | yes | todo |
| [T-206](T-206-workflow-tools.md) | Workflow-specific tools and adapter data | 2 | T-002, T-101 | workflow decision | standard | yes | todo |
| [T-301](T-301-support-agent.md) | Support agent and company brain | 3 | T-204, T-206 | LLM provider | standard | no | todo |
| [T-302](T-302-console-queue.md) | Handoff queue and audit timeline | 3 | T-204 | — | standard | yes | todo |
| [T-303](T-303-end-to-end-evaluation.md) | End-to-end evaluation | 3 | T-301, T-203 | — | judgment checkpoint | no | todo |
| [T-304](T-304-deploy-demo.md) | Deploy the demo | 3 | T-003, T-205, T-204 | hosting accounts (maintainer) | standard | yes | todo |
| [T-401](T-401-durable-cases.md) | Durable cases | 3 | T-204, T-302 | — | standard | yes | todo |
| [T-402](T-402-verifier-panel.md) | Risk-tiered verifier panel | 4 | T-004, T-303 | Tier 0 gate | standard | yes | todo |
| [T-403](T-403-coworker-agent.md) | Coworker agent | 4 | T-302 | Tier 0 gate | standard | yes | todo |
| [T-404](T-404-analytics-tab.md) | Analytics tab | 4 | T-303 | Tier 0 gate | standard | yes | todo |
| [T-405](T-405-fairness-tests.md) | Fairness and counterfactual tests | 4 | T-303, T-203 | Tier 0 gate | standard | yes | todo |
| [T-406](T-406-second-adapter.md) | Second MCP adapter and swap demo | 4 | T-206 | Tier 0 gate | standard | yes | todo |
| [T-407](T-407-flywheel-turn.md) | One offline flywheel turn | 3 | T-201, T-303 | — | standard | yes | todo |
| [T-408](T-408-policy-replay.md) | Console policy page with rule-and-replay | 3 | T-302 | — | standard | yes | todo |
| [T-501](T-501-readme-results.md) | README usage and results report | 5 | T-303 | — | standard | yes | todo |
| [T-502](T-502-release.md) | Release notes and tags | 5 | T-501 | maintainer approval | standard | yes | todo |
| [T-503](T-503-slides.md) | Slides | 5 | T-303 | — | judgment checkpoint | yes | todo |
| [T-504](T-504-video.md) | Video pitch (3 minutes or less) | 5 | T-304, T-503 | maintainer records | judgment checkpoint | yes | todo |
| [T-505](T-505-submission.md) | Submission | 5 | T-501 to T-504 | maintainer sends | standard | no | todo |
| [T-601](T-601-ag-ui-console.md) | AG-UI endpoint and CopilotKit console | Tier 2 | Tier 1 gate | — | standard | yes | todo |
| [T-602](T-602-verifier-streaming.md) | Live verifier streaming | Tier 2 | T-601 | — | standard | yes | todo |
| [T-603](T-603-verifier-lab.md) | Offline verifier lab | Tier 2 | T-303 | — | standard | yes | todo |
| [T-604](T-604-iso20022-xml.md) | ISO 20022 XML validation | Tier 2 | T-206 | — | standard | yes | todo |

The rule for T-101 is pre-registered; its status moves to `doing` when the analysis starts.

## Order at a glance

```
Wave 0:  T-000 ─► T-001 · T-002 · T-003 · T-004 · T-005          (no data needed)
Wave 1:  T-101 (workflow decision) ─► T-103 ─► T-106 ;  T-104 ;  T-102 ─► T-105
Wave 2:  T-201 · T-203 · T-204 · T-205 · T-206
Wave 3:  T-301 · T-302 · T-303 · T-304 · T-401 · T-407 · T-408   ── Tier 0 gate: deployed, results in README ──
Wave 4:  T-202 · T-402 … T-406                  (Tier 1, only after the gate)
Wave 5:  T-501 … T-505                          (submission)
Tier 2:  T-601 … T-604                          (only with room to spare)
```
