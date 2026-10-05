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
| Concept | thesis (Systems 1 → 3), architecture and governance retained; decisions 34–37 refine which experiments prove the evolutionary, AI-powered banking decision engine. These new roadmap decisions describe **planned** work, not measured or shipped features. README positioning avoids the word "gate" |
| Repository | `v0.1.0` released; since then every pull request through #60 is merged: decisions 16–32, the full-data findings, Wave 0, the hub, the customer app, the LLM client, deployment readiness, policy v2, the full-data inventory, labels and the evaluation harness. Merges are squash merges since #31. Submission cut (maintainer decision): T-106 keyed generation + sample reviews, T-201, and full T-303 runs are `not run` with named blockers (LLM keys); the tier-0 offline report stands as the measured result |
| Data findings `[measured]` | `contact_reason` repeats the six values of `reason_category`; the 171,321 transcripts hold only 42 distinct customer texts, the same under every category; all 36 transaction type × channel pairs occur, so fields look independently generated |
| Classifier text | team-generated, not the dataset transcripts (decision 16) |
| Workflow | **stuck payments, end to end** (decision 17, [DESIGN 6.1](DESIGN.md#61-the-workflow-stuck-payments-end-to-end)): explain, clarify, act under the Gate, investigate, follow up. |
| Data evidence | the analyst's pilot figures reconcile with the full data (same rates); links between tables are at chance. The analyst has left the project: the full-data pipeline run, the T-104 baseline and the six corrections are re-assigned to the maintainer; T-104 re-measured the full data (TSD-018) and matched every common headline cell of the analysis session's independent cross-check, preserved at `reports/baseline-independent/` |
| Full-data inventory and baseline | TSD-014 is merged (#50): the read-only 13-table scan counted 23,495,188 rows with no discrepancies; the aggregate report is in `reports/data-quality/full-inventory.md`. T-104 (TSD-018) is complete on `eval/baseline`: the guarded four-table run matched all 128 independent headline cells, a separate guarded call-table scan resolved the Web Chat channel and matched all 108 grouped-channel cells, and the measured baseline is published in `reports/baseline/` (aggregates only; the cross-check is preserved at `reports/baseline-independent/`). Five tables remain uncontracted. |
| Team | the maintainer governs the repository alone (all commits and PRs). The data analyst has left the project; tasks they owned are re-assigned to the maintainer in the backlog |
| Data access | read-only dataset credentials live in the cloud environment's variables; the access key id there had a one-character typo, so check it is 20 characters before relying on it |
| Code | **Merged:** TSD-000 (scaffold, `calvino.records`, `calvino.decision_log`, CI); TSD-001 (`calvino.policy`: `decide_route`, `decide_gate`, `replay_decision`, `policy/v1.yaml`); TSD-002 (`calvino.tools`: ten tools, `BankTools`, dataset adapter, hub-attached sessions, single-use confirmation tokens, JSON Schemas in `contracts/tools/`, fixture in `tests/fixtures/bank/`); TSD-005 (#31, `calvino.classifiers`: the real laya 0.3.24 router API behind `LayaClient`, question builders, temperature calibration with ECE/Brier and a reliability plot); **T-102 done (#24):** TSD-007: contracts for the eight tables Calvino uses, rules from DATA.md with severities, a DuckDB audit over Parquet or CSV (including the organizer's partitioned layout) and a lineage file. **Merged (#33):** TSD-003 (deployment skeleton: `calvino.api` demo service, HF Space Dockerfile, Next.js frontend, `docs/DEPLOY.md`), rebuilt from its spec after the cloud session's work proved unrecoverable. **Built, merged (#36):** TSD-004 (verifier), rebuilt from its spec on `feat/verifier`: versioned `customer-answer` rubric, evidence from tool results, five deterministic code checks, judge and Laya interfaces with scripted fakes, cascade with one retry, escalation and decision logging. Wave 0 is complete. **Built, merged (#37):** TSD-009 (hub, T-204): versioned stuck-payments playbook with per-stage tools, trusted test sessions, the LangGraph workflow with the five stages over the policy verdicts, the Gate with confirmation tokens and verified read-backs, `interrupt()` for approvals and the operator queue, investigate with gate-confirmed bank cases and handoff case files, the `HubService` facade with resume over a sqlite checkpointer, and the seeded acceptance scenarios with their scoreboard. **Built, merged (#38):** TSD-010 (customer app, T-205): the hub HTTP endpoints open behind the rate limit, the FR-7 cards from verified tool results, the per-turn decision trace, the deterministic TemplateAgent and the demo personas, and the Next.js customer screen (scenario buttons, confirm/deny bound to the exact parked action, operator resume, glass-box panel, ES/PT toggle). **Merged (#43):** TSD-012 (deployment readiness, T-304): the XFF rate-limit key, the live smoke check with offline tests, and the DEPLOY.md corrections; the live run waits on the maintainer's accounts. **Merged (#40, #41):** TSD-011 (`calvino.llm`: provider-agnostic chat client, OpenAI-compatible adapter, Hetzner config, `providers.yaml` and its catalogue check; and `OpenAiJudge` behind the verifier's `Judge` protocol). **Merged (#48):** `policy/v2.yaml`. **Merged (#55–#57):** TSD-015 (labels, splits, leakage rules, gold rubric); the first-50 gold sheet is 18/50 labelled. **Built (`feat/llm-agent`, TSD-016, T-301):** `calvino.hub.LlmAgent` (the model writes the reply, the harness plans), the hash-pinned `prompts/support-agent-v1.yaml`, and `run_evaluation.py` running the LLM agent and real judge when keys are set. With live Laya only 2 of 50 cases reach the agent (the rest escalate or clarify first, ORC-010/011 end at the Gate with a refusal card), so a full run does not yet measure the model. **Merged (#58–#59):** TSD-013 (evaluation harness, 50 cases); the committed tier0 report predates #59 and shows 22/37 outcome agreement, 13 unnecessary escalations and one missed escalation (ADV-002, prompt injection), with zero unsafe outcomes. **Merged (#83–#85):** TSD-022 (intent-driven visual investigation, T-207): speech-to-text, morph cards, CaseStudy dossier, audited CoT, and bilingual parity. **Implemented:** TSD-023 (operator workspace, T-302): System 3 human-in-the-loop workspace at `/console`, filterable `OperatorQueueTable`, detailed `OperatorCaseDossier`, Gate-block immutable `ActionApprovalBar`, split-view `AttributableReplyEditor`, and `GET /api/hub/cases` endpoint with fallback seeds |

| T-105 freshness fixture | **Merged (#81):** `calvino.data.freshness` provides synthetic-only source lineage, partition snapshots, stale-artifact checks, revision handling, split reassignment and frozen-set drift reports under TSD-021. Full repository checks passed before merge. No live data or production ingestion is involved. |
| T-206 cleaned-table adapter | **Implemented locally:** approved TSD-024 is complete on `feat/workflow-tools`; full offline checks pass. Only the labelled synthetic fixture was accessed. The branch has not been pushed; get separate maintainer approval before pushing. |
| LLM provider | decided (decisions 28 and 29): agent on Hetzner's Inference API with `Qwen/Qwen3.6-35B-A3B-FP8`, free with no account beyond a token; judge on OpenRouter with `deepseek/deepseek-v4-pro-0813`, a dated release, so it is pinnable where the Hetzner id is not. Client in `calvino.llm` (TSD-008), ids from the environment, the choice committed in `providers.yaml`; `clients_from_env` refuses to start if both models share a family. Pending: the two keys, an OpenRouter spending cap, and the T-106 A/B that confirms the agent model | The first live call is measured: both catalogue ids are served, 2.3-3.5 s warm and 4.9-6.1 s cold, and the served models are reasoning models (`providers.yaml`, 2026-10-03). The other served id (`Qwen3.8-27B`) has not answered within a 903 s budget, which makes it unmeasured rather than unusable, so it is not yet a second candidate for the T-106 A/B.
| Hosting | **no public link yet.** Decision 27 (free Gradio Space) and `docs/DEPLOY.md` (Docker Space + Vercel) disagree; pick one before creating accounts. T-305 is a spec only |
| Thesis-first roadmap | Documentation on `docs/thesis-roadmap` records the maintainer's scope decisions: T-202 fine-tuning and T-201 comparison; T-407 offline governed flywheel and T-408 policy replay/promotion scorecard; T-402 pre-execution veto comparison and T-603 human-authored verifier benchmark; T-405 paired fairness evidence; T-406 adapter swap and T-604 one mock ISO 20022 action exchange. T-206 is a full cleaned-table adapter. The live panel, ISO bank boundary, flywheel and adapter swap are **not implemented** by this docs change. T-305 stays emergency fallback; T-403/T-404/T-601/T-602 are future product surfaces |

## 2.1 Next actions

In order; items 1–3 block the submission.

| # | Action | Owner | Blocked by |
|---|---|---|---|
| 1 | Pick the deploy path (decision 27's Gradio Space or DEPLOY.md's Docker Space + Vercel), record it in DECISIONS.md, create the accounts and publish the link | maintainer | — |
| 2 | Portuguese coverage: PT scenarios and an evaluation slice (the brief requires ES and PT; the suite has none) | session | — |
| 3 | Re-run the evaluation after #59: `--suite tier0`, then `--suite all` for the bare-LLM ablation and the judge false-pass rate; finish the gold sheet (18/50) first | maintainer, session | 4 |
| 4 | Judge key: OpenRouter key with a spending cap (decision 28); agent token for Hetzner | maintainer | — |
| 5 | Tuning pass on the evaluation findings: the 13 unnecessary escalations and the missed escalation on ADV-002. **It also gates the LLM evaluation:** only 2 of 50 cases reach the agent until live laya stops over-escalating routine Spanish | session | 3 |
| 5b | A judge that answers inside the hub for build/test runs (the NVIDIA `deepseek-v4.1-flash` times out on every criterion); decision 39 proposes the choice | maintainer | — |
| 6 | Per-language thresholds as `policy/v3.yaml` (decision 33), when the hub reads per-language scores | session | 5 |
| 7 | Ask the organizers whether the dataset key should be rotated; fix the access key id in the environment (must be 20 characters) | maintainer | — |
| 8 | GitHub settings: squash merging only, automatic deletion of head branches, delete merged remote branches, and "Keep my email addresses private" (web merges carry the personal email) | maintainer | — |
| 9 | ~~T-104 on the full data, without treating category-level baselines as case-level labels~~ done (TSD-018 on `eval/baseline`): the measured baseline is published in `reports/baseline/` and reconciled with the cross-check preserved at `reports/baseline-independent/` | maintainer | — |
| 10 | README results per TSD-017 (#60, proposed), slides and the demo video | maintainer | 1, 3 |
| 11 | After the current deployed/evaluation blockers, specify and measure the thesis experiments in decisions 34–37; do not use hypothetical latency, thresholds, fairness gaps, false-pass rates or unsupported banking fields as Calvino results | sessions | T-103, T-106, T-303 |

## 2.2 What the analyst was asked for (round two)

**Dead:** the analyst has left the project and this delivery will not arrive. Kept for the record; if any item is still needed before the evaluation, the maintainer re-runs it.

1. **Full-data run:** `clean_all_tables.py --all` on the `data/` prefix; row counts per table checked against DATA.md. The two-week pilot window (17–30 June 2023) stays a labelled development subset; every published number comes from the full data.
2. **Six corrections to the analyst's write-up:** null `response_code` values move from workflow evidence to data quality; claimed amounts averaged per currency and converted to USD (mixing currencies gives about 2,600, about 680 in USD); web errors reported as a rate per page, not as "payment errors"; limits labelled as policy assumptions; the IP-country mismatch kept only as a demo rule; the Portuguese set uses MXN, COP, ARS or USD, never BRL.
3. **T-104 human baseline on the full data:** for calls (all and Transaccional; by country, channel and segment), first-contact resolution, escalation, follow-up, handle and wait time with nulls counted; for complaints (all and Transactions; by country and case type), resolution days, SLA breaches, compensation and claimed amounts. Cells under 30 cases are flagged.
4. **Review of the data-quality report** written by the analysis session, adding anything their validator found.
5. **Delivery folder:** `scripts/` (pipeline, baseline, permutation test), `tests/` with synthetic fixtures, `reports/baseline-independent/` and `reports/data-quality/` (aggregates only), and a notes file. Credentials from environment variables; no storage names; an evidence label on every number.

T-104's published figures were compared cell by cell with the analysis session's independent cross-check (`reports/baseline-independent/`): all 128 common headline cells matched.

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
- **Scoped attribution only:** the exact Factory co-author trailer is permitted on Markdown-only commits; other AI-tool attribution and all PR-description attribution remain blocked. Commits use the configured maintainer identity; never override it in an agent session.
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
| The pre-commit secret guard also blocks a test constant named like a key (`API_KEY = "test-…"`) and any edit to a line that lists a credential-shaped name such as the dataset's access key variables | the guard matches the shape of a changed line, not the intent; name unit-test values something else (`TEST_TOKEN`) and put new information on a new line instead of rewriting a guarded one |
| Laya's first call loads the checkpoint (20–25 s on CPU) | preload at startup; never load on the first request |
| A provider model id is not always a version: Hetzner serves bare ids that can be re-pointed at new weights, while OpenRouter offers dated releases such as `deepseek-v4-pro-0813` | prefer a dated id wherever the provider offers one, and record the catalogue with its date so a silent swap is visible in the log |
| Hetzner's other served model, `Qwen3.8-27B`, returned nothing inside a 903 s budget (600 s timeout, two retries), ending in a transport failure `[measured]` | this records **our patience, not a verdict on the model**: a DeepSeek id on another provider answered at 273 s, well after this client had already given up at 91 s, so treat the id as *unmeasured* and re-probe it with a long budget before ruling it out; `providers.yaml` keeps it as `no_answer_within_seconds` for exactly this reason |
| A one-word probe understates what the model costs: "Reply with exactly: OK" came back in 2.3-3.5 s, a real three-sentence customer reply in 20.0-26.1 s `[measured]` | size timeouts and demo expectations from a real draft; the probe is the honest cost of a health check and nothing else. `providers.yaml` keeps both, as `latency_ms_probe` and `draft_latency_ms`, because a single bare `latency_ms` read as the demo figure and was an order of magnitude out |
| The served models are **reasoning models**: a tight `max_tokens` is spent thinking, so the completion comes back with no `content` key and `finish_reason: length`, and a one-word answer still cost 109-116 output tokens `[measured]` | allow a real token budget; the adapter raises `LLM-TRUNCATED` and says so, because the same message as an unreadable response would send you hunting a fault that does not exist |
| NVIDIA's API trial queues large models past its own 300 s gateway: `deepseek-ai/deepseek-v4.1-flash` answered at 273 s and 299 s, and returned 504 at 302 s `[measured]` | streaming cannot rescue it, because zero bytes arrive before the limit and there is no chunk to send; treat a provider answering at the gateway boundary as unusable, and remember a retryable 504 makes one logical call cost `timeout x 3` |
| NVIDIA's `/v1/models` lists models the account cannot call: `google/gemma-3-4b-it` answers 404, "Function ... not found for account" `[measured]` | on that provider a catalogue check is necessary but not sufficient, so a passing `check_providers.py` is not proof a model is callable; the Hetzner check does rely on the catalogue being authoritative (decision 29) |
| NVIDIA's DeepSeek card documents a numeric `reasoning_effort` of 1-100, but the endpoint accepts a string and refuses a number: `reasoning_effort: 5` returns 400 "expected string or map" `[measured]` | `ReasoningEffort` sends `"low"`, which that endpoint accepts; a vendor card is not evidence of what a provider validates, and acceptance is still not honouring |
| Hetzner's Inference API caps 10 requests per 60 s per key `[vendor]`, and one case costs an agent call and a judge call | the client paces itself below the cap (`CALVINO_LLM_MAX_REQUESTS`); a live demo still needs the rate limit from PLAN.md, and OpenRouter stays the fallback because the service is experimental with no SLA |
| The dataset's text is templated and its fields look independently generated | never train on the transcripts; check any link between tables (time windows, joins) against a shuffled baseline before treating it as evidence |
| Teammate material can contain unmeasured figures, fields the dataset lacks, or storage names | verify every number on the full data before reuse; never copy storage names into the repository |
| PRs so far were merged with a merge commit, not a squash | until the repository allows squash only, remind the maintainer to pick "Squash and merge" |
| Sessions on cheaper models produced plausible but wrong work: the first TSD-002 put the customer id in the model-visible tool arguments and crashed on start; the first TSD-005 guessed Laya's API and its tests failed on a clean checkout | review every branch on a fresh checkout against its spec and the design rules before the PR, closest for security and model integration |
| The LLM agent's replies cost thousands of tokens and the judge on NVIDIA times out in the hub `[measured]` | one real explain turn: Qwen wrote a grounded Spanish reply in 29.5 s using 530 prompt and 3,064 completion tokens, so `COMPLETION_BUDGET` is 8,192 (2,048 ended `LLM-TRUNCATED`, with no reply). The NVIDIA judge returned `LlmTimeout` on all three judged criteria after 182 s, which fails closed and escalates; run build/test evaluations with a judge that answers, and read the header's "Judge in the hub" row |
| The cascade used to default a missing judge or Laya checker to fakes that pass everything | fixed (decision 40): a tier with no implementation fails closed as `unverified`, rubric v2 assigns nothing to the unbuilt Laya tier, and the keyless demo uses an explicit `NotRunJudge`; tests must pass `MockJudge()` themselves, and the report header's "Judge in the hub" row says what ran |
| A session pushed before rebasing on a `main` that had moved, so the PR conflicted | before approving a push, ask for `git fetch origin && git rebase origin/main` and a re-run of the checks |
| Personal email addresses and local paths reached a pushed branch (a plan file), and merges made in GitHub's web interface carry the maintainer's personal email | no personal emails or local paths in any file; turn on "Keep my email addresses private" in GitHub's email settings before merging |
| Planning drafts contained unmeasured figures (33 ms latency, F1 scores), BRL and PIX for a dataset without them, and dataset credentials | check every figure and field against DATA.md and the reports; never paste credentials into documents or chats; rotate a key that was exposed |
| `Stage` has no `tool` member (hard_rules, classifier, gate, verifier, human only), and `open_investigation` has no tool-side fraud or status check (its `check_eligible` is a no-op) | log tool refusals under `Stage.HARD_RULES` with the tool's rule id; case-opening eligibility is the Gate's job (`GATE-INELIGIBLE`), never the tool's |
| Hub graph tests that park a turn (`interrupt()`) fail without a checkpointer | build the graph with `InMemorySaver()` and resume with `Command(resume=…)` under the same thread id |
| Routing sends every agents turn to the explain stage; the act stage only exists once a write is proposed and the Gate promotes the turn | an explicit action request proposes its write from the explain step — a literal cancel/retry keyword scan, never a model (decision 10) |
| The TemplateAgent never picks between several problem payments (decision 10), so a message without a reference gets the picker question when the persona has more than one | scenario buttons for a single-payment flow cite the reference in the message (UC-1: `¿Por qué sigue pendiente E-MX-002?`) |
| The hub endpoints return 503 while `/api/demo/decide` works | the hub is disabled fail-closed: `CALVINO_CONFIRMATION_KEY` (32+ bytes) is missing, or the bundled bank fixture is unreadable |
| Behind Vercel's `/api` rewrite every request reaches the Space from the same egress IP, so a per-client rate limit keyed on the direct peer becomes one global cap for every judge | the guard keys on the first `X-Forwarded-For` entry when present (`client_key()` in `calvino.api.app`); set `CALVINO_DEMO_RATE_LIMIT=120` for the judging window; a spoofed header weakens only the limit (TSD-012, NFR-8) |

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
