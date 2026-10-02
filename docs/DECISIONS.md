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
