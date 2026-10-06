# Tasks: backlog and orchestration

*Every piece of remaining work, with its dependencies, so new sessions can pick it up. Wave 0 tasks have full specifications; later tasks have task cards that are turned into a specification as their first step. The workflow is chosen (decision 17), so every card can be specified now.*

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
- **Shared files:** each PR adds one line to `CHANGELOG.md` under `Unreleased` updates only its own row in this backlog (the one place that holds status), and adds a new spec to the list in `docs/specs/README.md`. Dependencies are added with `uv add`; if a rebase conflicts on `uv.lock`, run `uv lock` and commit the result, never a hand-merged lockfile.
- **Pull requests:** after the maintainer approves the push, the session gives the compare link (`https://github.com/moebious/factored-hackathon-2026-calvino/compare/main...<branch>?expand=1`) and a description that follows `.github/pull_request_template.md`. The maintainer opens the PR, so no tool adds an attribution footer that fails the `conventions` check.
- **Acceptance scenarios (decision 23):** `tests/scenarios/` holds AC-1 to AC-8 as seeded scenarios that run in CI with a scoreboard. A task's "done when" includes the scenarios it makes pass; a scenario that passes is never allowed to fail again.
- **Rebasing after another PR merges** rewrites the branch, so it needs a `--force-with-lease` push, which also needs the maintainer's approval.

### Session prompt template

Paste as the first message of a new session; replace the spec, branch and worktree:

```text
Implement docs/specs/TSD-NNN-<name>.md, following AGENTS.md. Start by reading docs/HANDOFF.md, AGENTS.md, the spec (including its "Workflow context" section), and the DESIGN.md sections and decisions it references.

Rules: branch <type>/<name> in its own worktree (.worktrees/<name>) from origin/main (if the worktree already exists, work in it); Conventional Commits authored as the maintainer (git config user.name "Kevin Vicent", user.email "624602+moebious@users.noreply.github.com"); only the exact Factory co-author trailer on Markdown-only commits as permitted by AGENTS.md, and no AI attribution in PR text; enable hooks with git config core.hooksPath .githooks. Tests need no network, GPU or dataset. Run uv run ruff check ., uv run ruff format --check ., uv run pytest and bash tests/git/test_git_rules.sh before reporting.

Before writing code, post your commit plan (an ordered list of small logical commits, each with its scope) and wait for my adjustments; then commit each step when it works, within the size limits in AGENTS.md.

Follow the shared-file and pull-request rules in docs/tasks/README.md. Never push without my explicit approval for that specific push. When done, report test results and the diff summary, and propose the push.
```

## Backlog

Status: `todo`, `spec` (specification written, awaiting approval), `doing`, `review` (PR open), `done`, `deferred` (future product surface, not a current gate). A `spec` marked as a fallback is not a substitute for the full demo.

**Proof versus implementation:** decisions 34–37 make Laya specialisation, governed offline learning/replay, pre-execution veto measurement, paired fairness evidence and the adapter/ISO boundary part of the current **thesis proof**. The cards describe work to do, not completed features or measured outcomes. Keep illustrative numbers, invented banking signals and vendor benchmark results out of Calvino's results. In particular, T-303's available report is an intermediate run; a skipped judge validation or bare-LLM ablation is not a completed protected measurement. T-305 is a decision-only emergency fallback, not T-304 completion.

Owner: **maintainer** (the core system and delivery). The data analyst has left the project; every task they owned is re-assigned to the maintainer, and the round-two delivery (HANDOFF 2.2) no longer happens. `done` rows keep the analyst as owner for the record.

| ID | Task | Wave | Depends on | Blocked by | Model | Parallel | Status | Owner |
|---|---|---|---|---|---|---|---|---|
| [T-000](../specs/TSD-000-scaffolding.md) | Python scaffolding and shared types | 0 | docs PRs merged | — | standard | no (first) | done | maintainer |
| [T-001](../specs/TSD-001-policy-engine.md) | Policy engine | 0 | T-000 | — | standard | yes | done | maintainer |
| [T-002](../specs/TSD-002-mcp-tools.md) | MCP tools and ISO 20022-aligned contracts | 0 | T-000 | — | standard | yes | done | maintainer |
| [T-003](../specs/TSD-003-deployment.md) | Deployment skeleton | 0 | T-000 | — | standard | yes | done | maintainer |
| [T-004](../specs/TSD-004-verifier.md) | Verifier framework | 0 | T-000 | — | standard | yes | done | maintainer |
| [T-005](../specs/TSD-005-laya-service.md) | Laya service and calibration | 0 | T-000 | — | standard | yes | done | maintainer |
| [T-011](../specs/TSD-011-llm-client.md) | LLM client and Hetzner provider | 0 | T-000 | — | standard | yes | done | maintainer |
| [T-101](T-101-contact-reason-analysis.md) | Contact-reason analysis and workflow decision | 1 | — | dataset access | judgment checkpoint | yes | done (decision 17) | maintainer |
| [T-102](../specs/TSD-007-data-contracts.md) | Data contracts, quality report and lineage | 1 | T-000 | dataset access | standard | yes | done | maintainer |
| [T-103](T-103-labels-splits.md) | Labels, splits and gold-set rubric implementation | 1 | T-101 | — | judgment checkpoint | no | done | maintainer |
| [T-104](T-104-human-baseline.md) | Reproducible full-data, category-level human baseline (not case-matched) | 1 | T-101, TSD-014, TSD-018 | — | standard | yes | done | maintainer |
| [T-105](T-105-freshness-fixture.md) | Corrected-record lineage, label and promotion-evidence integrity fixture | 1 | T-102 | — | standard | yes | done (#81) | maintainer |
| [T-106](T-106-message-set.md) | Disjoint training/calibration/test messages; reuse the frozen oracle contract | 1 | T-103; T-107 for gold-subset agreement | LLM provider keys (`not run`: keyed generation + sample reviews deferred to post-submission) | standard + maintainer review | no | todo | maintainer |
| [T-107](T-107-gold-annotation.md) | Maintainer gold annotation and agreement report | 1 | T-103 | — | judgment checkpoint | no | todo | maintainer |
| [T-201](T-201-classifier-evaluation.md) | Base/calibrated/fine-tuned Laya versus simpler baselines; threshold frontier | 2 | T-005, T-106, T-202 for final comparison; T-107 for reviewed gold metrics | `not run`: needs T-106 messages | judgment checkpoint | no | spec | maintainer |
| [T-202](T-202-laya-fine-tuning.md) | Reproducible open-weight Laya specialisation | 2 (thesis) | T-106 | GPU (maintainer runs the notebook) | judgment checkpoint | yes | done (run 1) | maintainer |
| [T-203](../specs/TSD-032-portuguese-test-set.md) | Translated held-out pairs and directly written Portuguese cases | 2 | T-106 | — | standard | yes | done (maintainer sign-off on review log pending) | maintainer |
| [T-204](T-204-calvino-hub.md) | Calvino hub | 2 | T-001, T-002, T-004, T-005 | — | judgment checkpoint | no | done | maintainer |
| [T-205](T-205-customer-app.md) | Customer app with Laya cards | 2 | T-003 | — | standard | yes | done | maintainer |
| [T-206](T-206-workflow-tools.md) | Full cleaned-table adapter for the existing workflow tools | 2 | T-002, T-101, T-102 | — | standard | yes | done (#92, #102) | maintainer |
| [T-207](T-207-intent-driven-customer-app.md) | Intent-driven customer experience and visual investigation | 2 | T-205, T-003 | — | standard | yes | done (#85) | maintainer |
| [T-208](../specs/TSD-029-human-request-hard-rule.md) | Hard rule for an explicit request for a person: coverage and false hits | 2 | T-106, T-001 | — | judgment checkpoint | yes | done | maintainer |
| [T-209](../specs/TSD-030-route-confidence-aggregation.md) | What the route's `confidence` score is computed from | 2 | T-106, T-201 | — | judgment checkpoint | yes | done | maintainer |
| [T-301](T-301-support-agent.md) | Bounded generative support agent with governed tools and policy retrieval | 3 | T-204, T-206 | — | standard | no | done | maintainer |
| [T-302](../specs/TSD-023-operator-console.md) | Full operator workspace, attributable reply/notes edits and audit timeline | 3 | T-204 | — | standard | yes | done | maintainer |

| [T-303](T-303-end-to-end-evaluation.md) | Actual-system evaluation, protected measurements and honest failure accounting | 3 | T-301, T-203 for final run; T-107 for gold-subset agreement | provider keys for protected measurements (`not run`: full runs incl. ablation and false-pass rate deferred; tier-0 offline report stands) | judgment checkpoint | no | doing | maintainer |
| [T-304](T-304-deploy-demo.md) | Deploy the demo | 3 | T-003, T-205, T-204 | hosting accounts (maintainer) | standard | yes | doing | maintainer |
| [T-305](T-305-gradio-demo-adapter.md) | Gradio decision-only emergency fallback, not the full app | fallback | T-005 | free Space (maintainer) | standard | yes | spec | maintainer |
| [T-306](T-306-frontend-deployment.md) | Frontend deployment and live interface execution | 3 | T-205, T-207, T-304 | Vercel deployment / maintainer run | standard | yes | doing | maintainer |
| [T-307](T-307-deployment-smoke-check-and-persistence.md) | Deployment smoke-check verification and persistence testing | 3 | T-304, T-306, T-401 | — | standard | yes | doing | maintainer |
| [T-401](../specs/TSD-025-durable-cases.md) | Parked turn and case-reference resume across restart | 3 | T-204, T-302 | — | standard | yes | done | maintainer |
| [T-402](T-402-verifier-panel.md) | Offline risk-tiered pre-execution veto comparison; runtime claim separately gated | 3 (thesis) | T-004, T-303 | labelled cases | judgment checkpoint | yes | todo | maintainer |
| [T-403](T-403-coworker-agent.md) | Coworker agent, only after measured operator need | future | T-302 | measured need | standard | yes | deferred | maintainer |
| [T-404](T-404-analytics-tab.md) | Interactive manager tab; metrics stay in reports | future | T-303 | measured need | standard | yes | deferred | maintainer |
| [T-405](../specs/TSD-033-fairness-and-counterfactuals.md) | Paired language/dialect evidence and policy-impact separation | 3 (thesis) | T-303, T-203 | — | judgment checkpoint | yes | spec | maintainer |
| [T-406](T-406-second-adapter.md) | Two synthetic formats, one unchanged hub/policy | 3 (thesis) | T-206 | — | standard | yes | todo | maintainer |
| [T-407](T-407-flywheel-turn.md) | One governed offline human-to-model update or rejection | 3 (thesis) | T-103, T-105, T-107, T-201, T-303, T-408 | reviewed labels | judgment checkpoint | yes | todo | maintainer |
| [T-408](T-408-policy-replay.md) | Offline policy verdict deltas and promotion scorecard | 3 (thesis) | T-201, T-303 | independent safety labels | judgment checkpoint | yes | todo | maintainer |
| [T-501](T-501-readme-results.md) | README usage and results report | 5 | T-303 | — | standard | yes | todo | maintainer |
| [T-502](T-502-release.md) | Final changelog and optional submission tag, no milestone backfill | 5 | T-501 | maintainer approval | standard | yes | todo | maintainer |
| [T-503](T-503-slides.md) | Slides | 5 | T-303 | — | judgment checkpoint | yes | todo | maintainer |
| [T-504](T-504-video.md) | Video pitch (3 minutes or less) | 5 | T-304, T-503 | maintainer records | judgment checkpoint | yes | todo | maintainer |
| [T-505](T-505-submission.md) | Submission | 5 | T-501 to T-504 | maintainer sends | standard | no | todo | maintainer |
| [T-601](T-601-ag-ui-console.md) | AG-UI endpoint and CopilotKit console | future | measured integration need | — | standard | yes | deferred | maintainer |
| [T-602](T-602-verifier-streaming.md) | Live verifier streaming | future | T-601 | — | standard | yes | deferred | maintainer |
| [T-603](T-603-verifier-lab.md) | Frozen financial-verifier benchmark, human-authored rubric revisions | 3 (thesis) | T-303 | reviewed labels | judgment checkpoint | yes | todo | maintainer |
| [T-604](T-604-iso20022-xml.md) | One governed action through mock ISO 20022 middleware and read-back | 3 (thesis) | T-206 | selected message profile | judgment checkpoint | yes | todo | maintainer |

The rule for T-101 is pre-registered; its status moves to `doing` when the analysis starts.

## Order at a glance

```
Wave 0:  T-000 ─► T-001 · T-002 · T-003 · T-004 · T-005          (no data needed)
Wave 1:  T-101 (done) ─► T-103 (done) ─► T-106 ; T-107 (gold review) ; T-104 ; T-102 (done) ─► T-105 (done)
Wave 2:  T-106 ─► T-202 ─► T-201 ; T-208 · T-209 ; T-203 (done) ; T-204 · T-205 (done) ─► T-207 ; T-206 (done #92, #102)
Wave 3:  T-301 · T-302 ─► T-401 ; T-303 ─► T-402 · T-405 · T-603 · T-408 ─► T-407
         T-206 ─► T-406 · T-604 ; T-304 (full public demo)
Wave 5:  T-501 · T-502 · T-503 · T-504 · T-505 (submission)
Fallback: T-305 (decision-only, never replaces T-304)
Future:   T-403 · T-404 · T-601 · T-602
```
