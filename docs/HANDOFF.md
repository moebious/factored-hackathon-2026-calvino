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
| Concept | frozen: thesis (Systems 1 → 3), architecture, governance, verifiers, decisions 1–17 |
| Repository | `v0.1.0` released (design, decisions, requirements, specs, task backlog, enforced git workflow); since then decisions 16–17, the full-data findings and the Python scaffold are merged |
| Data findings `[measured]` | `contact_reason` repeats the six values of `reason_category`; the 171,321 transcripts hold only 42 distinct customer texts, the same under every category; all 36 transaction type × channel pairs occur, so fields look independently generated |
| Classifier text | team-generated, not the dataset transcripts (decision 16) |
| Workflow | **stuck payments, end to end** (decision 17, [DESIGN 6.1](DESIGN.md#61-the-workflow-stuck-payments-end-to-end)): explain, clarify, act under the Gate, investigate, follow up. |
| Data evidence | the analyst's pilot figures reconcile with the full data (same rates); links between tables are at chance. In progress: the analyst runs the full-data pipeline, the T-104 baseline and six corrections; an analysis session writes the data-quality report and an independent baseline cross-check |
| Team | the maintainer governs the repository alone (all commits and PRs); a data analyst owns the data layer and delivers queries, scripts and aggregate tables for the maintainer to integrate |
| Data access | read-only dataset credentials live in the cloud environment's variables; the access key id there had a one-character typo, so check it is 20 characters before relying on it |
| Code | **TSD-000 done:** `uv` project, `calvino.records` (shared types) and `calvino.decision_log`, CI running ruff and pytest. **TSD-001 (policy engine) implemented:** `calvino.policy` with `decide_route`, `decide_gate`, `replay_decision` and `policy/v1.yaml`. **TSD-002 (MCP tools) implemented:** `calvino.tools` (ten tools, `BankTools`, dataset adapter, HMAC confirmation tokens), JSON Schemas in `contracts/tools/`, the synthetic fixture in `tests/fixtures/bank/`. Next: TSD-003, -004 and -005 in parallel agent sessions (any agent that reads AGENTS.md, local or cloud) |
| LLM provider | open (decision 6); the maintainer is arranging it. Blocks the message set (T-106) and the agent |
| Hosting | decided: Vercel (UI) + Hugging Face Space (backend) at `calvino.rubrica.dev`; accounts not created yet |

## 2.1 Next actions

In order. Item 9 can start at once.

| # | Action | Owner | Blocked by |
|---|---|---|---|
| 1 | Confirm the data-quality and baseline task in the analysis session so it runs | maintainer | — |
| 2 | Collect the analyst's round-two delivery (see [2.2](#22-what-the-analyst-was-asked-for-round-two)) and integrate it | maintainer, analyst | — |
| 3 | Compare the analyst's baseline with the analysis session's cross-check before publishing any baseline figure | maintainer, next session | 1, 2 |
| 4 | Choose the LLM provider and add its key to the environment | maintainer | — |
| 5 | Create the Hugging Face Space and Vercel accounts; add `HF_TOKEN` | maintainer | — |
| 6 | Fix the dataset access key id in the environment (must be 20 characters) | maintainer | — |
| 7 | Repository settings: squash merging only, automatic deletion of head branches | maintainer | — |
| 8 | ~~Implement TSD-000 (scaffolding)~~ done | — | — |
| 9 | Implement TSD-001, TSD-002, TSD-003, TSD-004 and TSD-005 in parallel sessions, one worktree each; if usage is tight, run TSD-001, -002 and -005 first | parallel sessions | — |
| 9b | ~~Record the baseline finding~~ done: DATA.md (findings and handling rules), DESIGN.md 7, PITCH slide 1, a note on decision 17, PLAN's cut order (flywheel, replay, follow-up; investigate never cut), T-303's target, and the data-quality rules in TSD-002, T-102, T-203 and T-206 | — | — |
| 10 | Message set (T-106), workflow tools (T-206), then the hub, the customer app, deployment, durable cases, policy replay, the flywheel turn and the evaluation with its ablation, per the backlog | sessions | 3, 4, 5 |

## 2.2 What the analyst was asked for (round two)

The analyst delivers files to the maintainer, who integrates them; the analyst does not commit. Due before the build reaches the evaluation.

1. **Full-data run:** `clean_all_tables.py --all` on the `data/` prefix; row counts per table checked against DATA.md. The two-week pilot window (17–30 June 2023) stays a labelled development subset; every published number comes from the full data.
2. **Six corrections to the analyst's write-up:** null `response_code` values move from workflow evidence to data quality; claimed amounts averaged per currency and converted to USD (mixing currencies gives about 2,600, about 680 in USD); web errors reported as a rate per page, not as "payment errors"; limits labelled as policy assumptions; the IP-country mismatch kept only as a demo rule; the Portuguese set uses MXN, COP, ARS or USD, never BRL.
3. **T-104 human baseline on the full data:** for calls (all and Transaccional; by country, channel and segment), first-contact resolution, escalation, follow-up, handle and wait time with nulls counted; for complaints (all and Transactions; by country and case type), resolution days, SLA breaches, compensation and claimed amounts. Cells under 30 cases are flagged.
4. **Review of the data-quality report** written by the analysis session, adding anything their validator found.
5. **Delivery folder:** `scripts/` (pipeline, baseline, permutation test), `tests/` with synthetic fixtures, `reports/baseline/` and `reports/data-quality/` (aggregates only), and a notes file. Credentials from environment variables; no storage names; an evidence label on every number.

Before any baseline figure is published, compare it with the analysis session's independent cross-check (next action 3).

## 2.3 Baseline finding (recorded, next action 9b)

From the analysis session's independent T-104 baseline on the full data `[measured]`, pending the analyst's own figures:

| | All calls | Transaccional |
|---|---|---|
| First-contact resolution | 76.7% | **91.5%** |
| Escalation | 10.0% | 9.9% |
| Follow-up | 34.8% | 22.1% |
| Median handle time | 291 s | 205 s |

Transactions-category complaints: 74.5% still open, SLA breached on 20.2%, median resolution 15 days among resolved ones; compensation is an amount present only on resolved or closed complaints, so its share needs an explicit denominator.

**What it changes:** decision 17 stands (it rests on volume, grounding and design fit), but the problem statement does: calls are high-volume and easy, so the target is to **match** the human 91.5% at zero unsafe outcomes with lower time and cost; the improvement story is the investigation stage. Changes in investigation time can only be *projected*, never claimed as measured.



Beyond AGENTS.md, learned while shaping the project:

- **Small logical commits, planned first.** Post the commit plan before coding; commit each step; the size limits are enforced. One 38-file, 4,000-line commit made TSD-002 hard to review.
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
| Creating a PR through an agent's GitHub tools appends a "Generated by …" footer, which the `conventions` check rejects | agents never open PRs (AGENTS.md); push, then give the maintainer the compare link and the description |
| PRs merged with a merge commit instead of squash | use **Squash and merge**; set it as the only merge method in repository settings |
| `git cherry-pick` has no `-q` flag; a script using it silently built empty branches | verify branch contents (`git diff --stat`) before any push |
| A commit subject over 72 characters | run `scripts/git/check-commit-msg.sh` or rely on the `commit-msg` hook |
| Environment variable with a truncated value (19-character key id) | check lengths without printing values; new values only reach new sessions |
| Some sites are blocked by the environment's network policy (for example the LangChain blog) | ask the maintainer for a PDF, or for the domain to be allowed |
| The pre-commit secret guard flagged its own test fixtures | fixtures split fake secrets with `""` so files never contain a complete one |
| Laya's first call loads the checkpoint (20–25 s on CPU) | preload at startup; never load on the first request |
| The dataset's text is templated and its fields look independently generated | never train on the transcripts; check any link between tables (time windows, joins) against a shuffled baseline before treating it as evidence |
| Teammate material can contain unmeasured figures, fields the dataset lacks, or storage names | verify every number on the full data before reuse; never copy storage names into the repository |
| PRs so far were merged with a merge commit, not a squash | until the repository allows squash only, remind the maintainer to pick "Squash and merge" |

## 5. Environment notes

- Python 3.11, `uv`, 4 CPU cores, about 15 GB RAM, **no GPU** (fine-tuning, a Tier 1 task, runs on Kaggle).
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
