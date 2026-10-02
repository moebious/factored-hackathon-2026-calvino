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
| Concept | frozen: thesis (Systems 1 → 3), architecture, governance, verifiers, decisions 1–26. Positioning: an evolutionary, AI-powered decision engine for banking customer service (README, PITCH, DESIGN 2); the README avoids the word "gate" |
| Repository | `v0.1.0` released; since then decisions 16–26, the full-data findings and their handling rules (#19), the Python scaffold, the policy engine (#20) and the MCP tools (#21) are merged |
| Data findings `[measured]` | `contact_reason` repeats the six values of `reason_category`; the 171,321 transcripts hold only 42 distinct customer texts, the same under every category; all 36 transaction type × channel pairs occur, so fields look independently generated |
| Classifier text | team-generated, not the dataset transcripts (decision 16) |
| Workflow | **stuck payments, end to end** (decision 17, [DESIGN 6.1](DESIGN.md#61-the-workflow-stuck-payments-end-to-end)): explain, clarify, act under the Gate, investigate, follow up. |
| Data evidence | the analyst's pilot figures reconcile with the full data (same rates); links between tables are at chance. In progress: the analyst runs the full-data pipeline, the T-104 baseline and six corrections; an analysis session writes the data-quality report and an independent baseline cross-check |
| Team | the maintainer governs the repository alone (all commits and PRs); a data analyst owns the data layer and delivers queries, scripts and aggregate tables for the maintainer to integrate |
| Data access | read-only dataset credentials live in the cloud environment's variables; the access key id there had a one-character typo, so check it is 20 characters before relying on it |
| Code | **Merged:** TSD-000 (scaffold, `calvino.records`, `calvino.decision_log`, CI); TSD-001 (`calvino.policy`: `decide_route`, `decide_gate`, `replay_decision`, `policy/v1.yaml`); TSD-002 (`calvino.tools`: ten tools, `BankTools`, dataset adapter, hub-attached sessions, single-use confirmation tokens, JSON Schemas in `contracts/tools/`, fixture in `tests/fixtures/bank/`). **Waiting for the maintainer's push approval in their sessions:** TSD-004 (verifier) and TSD-003 (deployment); both must rebase on `main` and split commits for the size check first. **Being fixed after review:** TSD-005 (Laya service): wrap the real `laya` API, skip real-model tests when absent, move `FakeLaya` to tests with a startup guard, real Spanish and Portuguese synthetic calibration set. **T-102 done (#24):** TSD-007: contracts for the eight tables Calvino uses, rules from DATA.md with severities, a DuckDB audit over Parquet or CSV (including the organizer's partitioned layout) and a lineage file |
| LLM provider | decided (decision 20): open models only, a Qwen model for the agent and a DeepSeek model as the judge; Hugging Face Inference Providers proposed, pending the maintainer's account with billing and a spending cap (OpenRouter is the fallback) |
| Hosting | decided: Vercel (UI) + Hugging Face Space (backend) at `calvino.rubrica.dev`; accounts not created yet |

## 2.1 Next actions

In order. Items 3, 4 and 6 can start at once.

| # | Action | Owner | Blocked by |
|---|---|---|---|
| 1 | Create the Hugging Face account and Space; enable Inference Providers billing with a spending cap; check the Qwen and DeepSeek models are available; add `HF_TOKEN` (confirms decision 20). Create the Vercel project | maintainer | — |
| 2 | Ask the organizers whether the dataset key should be rotated (it appeared in a planning document pasted into an external chat); fix the access key id in the environment (must be 20 characters) | maintainer | — |
| 3 | Approve the pushes of TSD-004 and TSD-003 after each rebases on `main` and splits its commits; TSD-005 after its fixes; review each branch against its spec's "done when" | maintainer, next session | — |
| 4 | ~~Run the contract audit on the full data~~ done: passed, counts in `reports/data-quality/` (Contract audit). Delete the old `data/contracts` branch on GitHub | maintainer | — |
| 5 | Collect the analyst's round-two delivery (see [2.2](#22-what-the-analyst-was-asked-for-round-two)) and compare its baseline with the analysis session's cross-check before publishing any baseline figure | maintainer, analyst | — |
| 6 | Acceptance scenarios (decision 23): the oracle table, `tests/scenarios/` with AC-1 to AC-8 and the CI scoreboard | next session | — |
| 7 | Message set (T-106), then the hub (T-204, with per-stage tools, the playbook file and trusted test sessions), the support agent, the customer app, deployment, durable cases and the evaluation with its bare-LLM ablation, per the backlog | sessions | 1, 6 |
| 8 | `policy/v2.yaml` with per-language thresholds (decision 22), when the hub reads per-language scores | session | 7 |
| 9 | Repository settings: squash merging only, automatic deletion of head branches; delete merged remote branches | maintainer | — |

## 2.2 What the analyst was asked for (round two)

The analyst delivers files to the maintainer, who integrates them; the analyst does not commit. Due before the build reaches the evaluation.

1. **Full-data run:** `clean_all_tables.py --all` on the `data/` prefix; row counts per table checked against DATA.md. The two-week pilot window (17–30 June 2023) stays a labelled development subset; every published number comes from the full data.
2. **Six corrections to the analyst's write-up:** null `response_code` values move from workflow evidence to data quality; claimed amounts averaged per currency and converted to USD (mixing currencies gives about 2,600, about 680 in USD); web errors reported as a rate per page, not as "payment errors"; limits labelled as policy assumptions; the IP-country mismatch kept only as a demo rule; the Portuguese set uses MXN, COP, ARS or USD, never BRL.
3. **T-104 human baseline on the full data:** for calls (all and Transaccional; by country, channel and segment), first-contact resolution, escalation, follow-up, handle and wait time with nulls counted; for complaints (all and Transactions; by country and case type), resolution days, SLA breaches, compensation and claimed amounts. Cells under 30 cases are flagged.
4. **Review of the data-quality report** written by the analysis session, adding anything their validator found.
5. **Delivery folder:** `scripts/` (pipeline, baseline, permutation test), `tests/` with synthetic fixtures, `reports/baseline/` and `reports/data-quality/` (aggregates only), and a notes file. Credentials from environment variables; no storage names; an evidence label on every number.

Before any baseline figure is published, compare it with the analysis session's independent cross-check (next action 5).

## 2.3 Baseline finding (recorded)

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
| Sessions on cheaper models produced plausible but wrong work: the first TSD-002 put the customer id in the model-visible tool arguments and crashed on start; the first TSD-005 guessed Laya's API and its tests failed on a clean checkout | review every branch on a fresh checkout against its spec and the design rules before the PR, closest for security and model integration |
| A session pushed before rebasing on a `main` that had moved, so the PR conflicted | before approving a push, ask for `git fetch origin && git rebase origin/main` and a re-run of the checks |
| Personal email addresses and local paths reached a pushed branch (a plan file), and merges made in GitHub's web interface carry the maintainer's personal email | no personal emails or local paths in any file; turn on "Keep my email addresses private" in GitHub's email settings before merging |
| Planning drafts contained unmeasured figures (33 ms latency, F1 scores), BRL and PIX for a dataset without them, and dataset credentials | check every figure and field against DATA.md and the reports; never paste credentials into documents or chats; rotate a key that was exposed |

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
