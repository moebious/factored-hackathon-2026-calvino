# Handoff: start here

*For any new working session, human or coding agent. Read this first, then AGENTS.md. Update the "Current state" section whenever it changes.*

## 1. Read in this order

1. [AGENTS.md](../AGENTS.md): rules for working in this repository (non-negotiable).
2. This file: state, preferences, pitfalls.
3. [BRD.md](BRD.md) → [PRD.md](PRD.md) → [DESIGN.md](DESIGN.md): why, what, how it is designed.
4. [tasks/README.md](tasks/README.md): the backlog and how work is picked up.
5. The spec or task card you were asked to implement, and the documents it references.

Supporting material: [GLOSSARY.md](GLOSSARY.md), [DATA.md](DATA.md), [BRIEF-COVERAGE.md](BRIEF-COVERAGE.md), [references/](references/README.md), [PITCH.md](PITCH.md), [DECISIONS.md](DECISIONS.md) (including rejected alternatives).

## 2. Current state

Keep this section current; it is the first thing a new session trusts.

| Area | State |
|---|---|
| Concept | frozen: thesis (Systems 1 → 3), architecture, governance, verifiers, decisions 1–15 |
| Repository | `v0.1.0` released (design, decisions, requirements, specs, task backlog, enforced git workflow) |
| Data findings `[measured]` | `contact_reason` repeats the six values of `reason_category`; the 171,321 transcripts hold only 42 distinct customer texts, the same under every category; all 36 transaction type × channel pairs occur, so fields look independently generated |
| Classifier text | team-generated, not the dataset transcripts (decision 16) |
| Workflow | **stuck payments, end to end** (decision 17, [DESIGN 6.1](DESIGN.md#61-the-workflow-stuck-payments-end-to-end)): explain, clarify, act under the Gate, investigate, follow up. Decisions 16 and 17 and the full-data findings are on branch `docs/workflow-decision` until merged |
| Data evidence | the analyst's pilot figures reconcile with the full data (same rates); links between tables are at chance. In progress: the analyst runs the full-data pipeline, the T-104 baseline and six corrections; an analysis session writes the data-quality report and an independent baseline cross-check |
| Team | the maintainer governs the repository alone (all commits and PRs); a data analyst owns the data layer and delivers queries, scripts and aggregate tables for the maintainer to integrate |
| Data access | read-only dataset credentials live in the cloud environment's variables; the access key id there had a one-character typo, so check it is 20 characters before relying on it |
| Code | none yet; the first build task is [TSD-000](specs/TSD-000-scaffolding.md) |
| LLM provider | open (decision 6); the maintainer is arranging it. Blocks the message set (T-106) and the agent |
| Hosting | decided: Vercel (UI) + Hugging Face Space (backend) at `calvino.rubrica.dev`; accounts not created yet |

## 2.1 Next actions

In order. Items 8 and 9 do not depend on the workflow and can start at once.

| # | Action | Owner | Blocked by |
|---|---|---|---|
| 1 | Confirm the data-quality and baseline task in the analysis session so it runs | maintainer | — |
| 2 | Collect the analyst's round-two delivery (full-data pipeline, corrections, baseline, scripts and tests) and integrate it | maintainer, analyst | — |
| 3 | Merge `docs/workflow-decision` (decisions 16 and 17, data findings); compare the analyst's baseline with the cross-check before publishing any baseline figure | maintainer, next session | — |
| 4 | Choose the LLM provider and add its key to the environment | maintainer | — |
| 5 | Create the Hugging Face Space and Vercel accounts; add `HF_TOKEN` | maintainer | — |
| 6 | Fix the dataset access key id in the environment (must be 20 characters) | maintainer | — |
| 7 | Repository settings: squash merging only, automatic deletion of head branches | maintainer | — |
| 8 | Implement TSD-000 (scaffolding) | any session | — |
| 9 | Implement TSD-001, TSD-002, TSD-004 and TSD-005 in parallel sessions | parallel sessions | 8 |
| 10 | Message set (T-106), workflow tools (T-206), then the hub, the customer app, deployment, durable cases, policy replay, the flywheel turn and the evaluation with its ablation, per the backlog | sessions | 3, 4, 5 |

## 3. Maintainer preferences

Beyond AGENTS.md, learned while shaping the project:

- **The maintainer decides every push.** Commit locally, then say what you would push, where and why, and wait. This includes PRs, branches, tags and deletions.
- **Explain before acting** on anything structural (renames, restructures, history rewrites). Offer options with a recommendation.
- **New work goes in new PRs.** Don't add unrelated commits to an open PR.
- **Some files are drafted but not committed** until the maintainer says so. Ask when unsure.
- **No dates or times on plan goals.** Plans are ordered phases and gates.
- **No AI-tool attribution** anywhere, and commits authored as the maintainer.
- **Avoid churn:** don't rename committed files without a strong reason.
- **Honesty over polish:** evidence labels on claims; say when something is a hypothesis, vendor claim or estimate.

## 4. Pitfalls already hit

| Pitfall | What to do |
|---|---|
| A stacked PR was merged into its base branch instead of `main`, so its changes never reached `main` | keep stacked PRs as drafts; merge only after GitHub retargets them to `main`; enable automatic deletion of head branches |
| Creating a PR through the GitHub tools appends a "Generated by …" footer, which the `conventions` check rejects | push the branch and give the maintainer the compare link and the description to paste, so the PR opens without the footer and without a red first run |
| PRs merged with a merge commit instead of squash | use **Squash and merge**; set it as the only merge method in repository settings |
| `git cherry-pick` has no `-q` flag; a script using it silently built empty branches | verify branch contents (`git diff --stat`) before any push |
| A commit subject over 72 characters | run `scripts/git/check-commit-msg.sh` or rely on the `commit-msg` hook |
| Environment variable with a truncated value (19-character key id) | check lengths without printing values; new values only reach new sessions |
| Some sites are blocked by the environment's network policy (for example the LangChain blog) | ask the maintainer for a PDF, or for the domain to be allowed |
| The pre-commit secret guard flagged its own test fixtures | fixtures split fake secrets with `""` so files never contain a complete one |
| Laya's first call loads the checkpoint (20–25 s on CPU) | preload at startup; never load on the first request |
| The dataset's text is templated and its fields look independently generated | never train on the transcripts; check any link between tables (time windows, joins) against a shuffled baseline before treating it as evidence |
| Teammate material can contain unmeasured figures, fields the dataset lacks, or storage names | verify every number on the full data before reuse; never copy storage names into the repository |

## 5. Environment notes

- Python 3.11, 4 CPU cores, about 15 GB RAM, **no GPU** (fine-tuning runs on Kaggle).
- Reachable: PyPI, the Hugging Face Hub and its file CDN, GitHub through the provided tools.
- `laya` 0.3.23 installs and runs on CPU; about 0.33–0.38 s per call after loading `[measured]`.
- Chromium is installed; Mermaid diagrams can be rendered with `npx @mermaid-js/mermaid-cli` to check they parse.
- Commands that wait on GitHub events should not poll; PR activity arrives as notifications.

## 6. Judgment checkpoints

These steps carry the most risk; use the strongest model available or have the maintainer review the reasoning before committing:

1. Applying the workflow decision rule (TSD-006).
2. Labels, splits and leakage rules.
3. Thresholds chosen by expected cost, and calibration per language.
4. Integrating the hub (where independently built parts meet).
5. Interpreting evaluation results (sample sizes, offline vs simulated vs projected, fairness).
6. The pitch: slides and video script.

## 7. Ending a session

Before stopping: commit (don't push without approval), update "Current state" above if it changed, and tell the maintainer what is ready to push, what is blocked, and what the next task is.
