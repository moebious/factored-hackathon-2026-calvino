# Decision Log

Short, dated records of design decisions. Newest last. Each entry says what was decided and why. A decision that changes later gets a new entry rather than an edit.

| # | Date | Decision | Reason | Status |
|---|---|---|---|---|
| 1 | 2026-10-01 | **LangGraph** for orchestration (instead of the Pi SDK used in the reference tutorial) | Python, alongside the data and evaluation work; checkpointer + `interrupt()` give durable cases and human-in-the-loop | accepted |
| 2 | 2026-10-01 | **Laya** as the System One model (instead of TypeSafe Jev) | Open weights (Apache 2.0) and self-hosted, so customer text never leaves the bank; multilingual; can be fine-tuned and recalibrated on our data | accepted |
| 3 | 2026-10-01 | Pin **`laya-multilingual`** for customer text | One calibrated model for every customer, regardless of language; avoids per-language checkpoint switching | accepted, to be validated per question type |
| 4 | 2026-10-01 | **Deterministic policy floor:** Laya gives probabilities, a versioned policy function decides; hard rules run first and always win | Auditable, replayable verdicts; no single probabilistic signal decides anything with consequences | accepted |
| 5 | 2026-10-01 | Customer-service **workflow** | To be chosen against contact-reason volumes and resolution/escalation rates in the data | open |
| 6 | 2026-10-01 | **LLM provider** and **demo UI depth** | Deferred; the LLM interface stays provider-agnostic | open |
| 7 | 2026-10-01 | **Git workflow:** GitHub Flow, Conventional Commits, squash merges, rebase-to-sync on own branches, `--force-with-lease` only, versioned hooks + CI sharing one checker | Small, readable history for reviewers; the same rules enforced locally and in CI. Not adopted: GitFlow (one version line, no parallel maintenance), `--no-ff` merges (squash keeps `main` one commit per PR), Git LFS (model weights and data are never committed), shared aliases (personal preference) | accepted |
| 8 | 2026-10-01 | **One worktree per branch; no commits on `main`** (bare-repository layout recommended; `.worktrees/` in other clones), enforced by `pre-commit`/`pre-push` hooks, a `main-guard` workflow and branch protection | Branches never share a working directory, so parallel work by the maintainer and coding agents can't collide; `main` only changes through reviewed, merged pull requests | accepted |
| 9 | 2026-10-02 | **MCP as the bank-core integration boundary:** one dataset adapter for the demo; adapters for real cores behind the same tools; adapter conformance tests; a second small adapter to prove the swap (Tier 1) | Decouples the hub from any one bank core; access checks live in the tool layer, as the brief requires | accepted |
| 10 | 2026-10-02 | **Demo link is a glass-box web app** at `calvino.rubrica.dev`: Laya-chosen cards from a fixed catalog (Shapeshift pattern), a glass-box panel showing scores, rules and verified tool calls, scenario buttons, ES/PT toggle. Next.js on Vercel, backend on a Hugging Face Space with keep-alive and baked weights. Supersedes the UI part of #6 | Judges see the thesis working within seconds; the UI itself is a verdict, so nothing on screen is free-form generation | accepted |
| 11 | 2026-10-02 | **Calvino Console** for operators, following OpenBot's philosophy (decided before, recorded after; refusals name their rule; take control) without computer use or per-agent sandboxes. CopilotKit/AG-UI in Tier 2 | Human-in-the-loop and explainability made visible; keeps the demo light enough to host | accepted |
| 12 | 2026-10-02 | **ISO 20022-aligned tool contracts** (entry shapes from camt.053/054; investigations camt.027/029; ISO 4217, 3166, 18245 codes). "Aligned", not "compliant" | One canonical data model across adapters, precise deterministic verifier checks, credibility with banks. Weighs toward a payments workflow, since cards still mostly use ISO 8583 | accepted |
| 13 | 2026-10-02 | **Calvino is the hub** of a hub-and-spoke architecture; spokes never talk directly. LangGraph and Deep Agents throughout (Pi dropped); AWS (VPC, API Gateway, containers, Bedrock) as the documented production reference | One governed place for decisions, gating, verification and audit; one runtime and language | accepted |
| 14 | 2026-10-02 | **Verifiers:** rubric cascade (code → Laya → one batched LLM judge) for every output; a risk-tiered panel of specialist verifiers judging per criterion for high-risk actions (Tier 1); an offline verifier lab that tunes rubrics from traces; an open model as the runtime judge | Efficient verification after the LangChain and Harvey study, optimised for false passes | accepted |
| 15 | 2026-10-02 | **Agent scope:** support chat fully built (Tier 0); company brain as a retrieval tool or subagent (Tier 0–1); coworker preparing cases for operators (Tier 1) | Depth on one workflow; every agent serves an explicit brief item | accepted |
| 16 | 2026-10-02 | **Classifier text is team-generated; dataset transcripts are not model input.** Laya is calibrated, fine-tuned and evaluated on a labelled set of Spanish and Portuguese customer messages, drafted with an LLM from dataset scenarios (personas, transactions, complaints) and reviewed by hand, all labelled synthetic. The dataset supplies the structured context the tools read, the proxy outcomes and the human baseline. The templated transcripts are reported as a data-quality finding. TSD-006 amended to match | The 171,321 transcripts hold only 42 distinct customer texts, identical across all six contact categories `[measured]`: any model trained on them learns the template, and its accuracy would mean nothing. Guards against generated text being too easy: separate generation prompts for training and test, adversarial rewordings, a hand-written subset, and the hand-labelled gold set | accepted |

## Alternatives considered and rejected

Recorded so they are not re-proposed without new information. Reopening one needs a new decision entry above.

| Alternative | Rejected because | Related decision |
|---|---|---|
| TypeSafe **Jev** as the System One model | closed, hosted API: customer text would leave the bank; can't be fine-tuned or recalibrated on our data | 2 |
| **Pi SDK** (TypeScript) harness alongside Python agents | a second language and runtime for one person to maintain; LangGraph covers the same hooks | 1, 13 |
| **QLoRA** for fine-tuning Laya | built for very large generative models; Laya is a 322M-parameter encoder, where full fine-tuning or LoRA is simpler and safer | 13 |
| **AWS Lambda** for the hub and Laya | CPU only, cold starts, about 1 GB of model to load; containers serve it with steady latency | 13 |
| **LLM-generated UI** (free-form generative components) | an LLM choosing the interface is the free-form behaviour Calvino avoids; a fixed card catalog chosen by Laya keeps the UI a verdict | 10 |
| **OpenBot / OpenDots machinery** (computer per agent, browser, terminal, sandboxes, Postgres, CopilotKit Intelligence) | too heavy to host for the demo, alpha software, and general-purpose computer access widens the attack surface of a banking agent; only the philosophy is kept | 11 |
| **Agentic verifiers** for every output | adds cost and latency and makes false-pass rates hard to measure; kept only as a risk-tiered panel for high-risk actions | 14 |
| Several **LLM agents debating** or negotiating verdicts | verdicts are combined by a fixed rule in the hub, never by a model; spokes don't talk to each other | 13, 14 |
| **Cloudflare Agents SDK** | not needed alongside LangGraph Deep Agents | 13 |
| **Gradio / Streamlit-only** demo as the final UI | doesn't show the thesis; kept only as a fallback if the card UI slips | 10 |
| **Card disputes as the ISO 20022 showcase** | card networks still mostly use ISO 8583; ISO 20022 fits payments and investigations better | 12 |
| Buying **calvino.sh** for the demo | `calvino.rubrica.dev` is already owned | 10 |
| Individual **ADR files** instead of this log | churn for a short project; this table records the same decision, reason and status | — |
| Renaming DESIGN.md to **SDD.md** | no benefit, link churn, and "SDD" also means spec-driven development; the file is labelled as the software design document instead | — |
| Classic **GitFlow**, `--no-ff` merges, Git LFS, shared aliases | see decision 7 | 7 |
| Training or evaluating classifiers on the **dataset transcripts** | 42 templated texts shared by every category; results would only measure the template | 16 |
