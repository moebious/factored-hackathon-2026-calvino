# AGENTS.md

Instructions for coding agents (and humans) working on this repository. Read this before making changes.

**New session? Start with [docs/HANDOFF.md](docs/HANDOFF.md):** current state, the maintainer's preferences, pitfalls already hit, and where everything is.

## Project

**Project Calvino** is an AI-first banking customer service system built around a domain-specific harness: a System One model (Laya) gives calibrated probabilities, a deterministic policy turns them into verdicts, an LLM handles only the language work, and humans step in where accountability is required.

- Business requirements: [docs/BRD.md](docs/BRD.md)
- Product requirements: [docs/PRD.md](docs/PRD.md)
- Design: [docs/DESIGN.md](docs/DESIGN.md)
- Technical specifications: [docs/specs/](docs/specs/README.md) (implement one spec per pull request)
- Decision log: [docs/DECISIONS.md](docs/DECISIONS.md)
- Build plan: [docs/PLAN.md](docs/PLAN.md) and roadmap: [docs/ROADMAP.md](docs/ROADMAP.md)

## Repository layout

Application directories are planned and created as code lands; update this section when they do.

| Path | Contents |
|---|---|
| `src/calvino/` | Python package: `records` (shared types), `decision_log`, and the `api`, `classifiers`, `data`, `evaluation`, `hub`, `llm`, `policy`, `tools` and `verifier` subpackages |
| `frontend/` | Next.js customer app and operator view (planned; CopilotKit / AG-UI console in Tier 2) |
| `policy/` | Versioned policy files (`v1.yaml`, `v2.yaml`, `v3.yaml`; v3 is the default): every threshold and limit the policy engine reads |
| `evaluation/` | Versioned evaluation case files (`evaluation/cases/`, TSD-013): synthetic, reviewed, scored against the oracle |
| `reports/` | Committed run outputs: evaluation reports (`reports/eval/`, from `scripts/run_evaluation.py`), data-quality findings and baselines |
| `providers.yaml` | The committed record of which model answers each language role, on which provider, and what that provider served on the date it was checked (decision 29). Keys are never here |
| `contracts/` | Generated JSON Schemas of the tool contracts (`contracts/tools/`, from `scripts/export_tool_schemas.py`) and the data contracts with their lineage (`contracts/data/`, from `scripts/export_data_schemas.py`) |
| `tests/` | `tests/calvino/` mirrors `src/calvino/` (pytest); `tests/fixtures/` holds small synthetic fixtures; `tests/git/` tests the git rule scripts |
| `pyproject.toml`, `uv.lock` | Python project configuration and locked dependencies (managed with `uv`) |
| `scripts/` | Developer scripts; `scripts/git/` holds the commit-message checker shared by hooks and CI |
| `.githooks/` | Versioned git hooks (`pre-commit`, `commit-msg`, `pre-push`), enabled with `git config core.hooksPath .githooks` |
| `.worktrees/` | Linked worktrees in non-bare clones. **Git-ignored** |
| `docs/` | Requirements (BRD, PRD), design, specifications, decisions, plan, roadmap |
| `data/` | Local datasets at the repository root. **Git-ignored, never committed** |

## Repository standards

1. **README.** It explains what the project does, why, and how to get it running. Whenever setup changes, update the run instructions in the same commit and make sure they still work.
2. **License.** The project is MIT-licensed (`LICENSE`). Don't add code or assets under incompatible licenses. Note third-party licenses where relevant (e.g. Laya is Apache 2.0).
3. **Clean repository.** Code, assets and config live in a sensible structure (see the layout above). Never commit OS files (`.DS_Store`, `Thumbs.db`), editor configs (`.vscode/`, `.idea/`), virtual environments, `node_modules/`, build artifacts, logs or model weights. `.editorconfig` is the only shared formatting config. If something unwanted shows up in `git status`, extend `.gitignore` instead of committing it.
4. **Clean history.** Each commit groups one coherent change and says so in its message. No "fix some things", "fix fixes" or revert chains: tidy work-in-progress commits locally before pushing (fold fixups into the commit they belong to, never several steps into one big commit). See [Day-to-day commits](#day-to-day-commits).
5. **Comments.** Every file and class starts with a few lines saying what it does. Comment anything surprising: thresholds, workarounds, Laya quirks, deliberate trade-offs. Don't leave commented-out code.
6. **Tests.** Add or extend tests with every change. Every policy function and every tool permission check has unit tests that run without model calls. Tests must not need network access, a GPU or the real dataset.

## Git workflow

Branching strategy: **GitHub Flow**. `main` is always releasable; all work happens on short-lived branches merged through pull requests. (GitFlow-style release branches are not used: there is one version line and no parallel maintenance.)

These rules are enforced twice, by the same script (`scripts/git/check-commit-msg.sh`): locally by git hooks (see [Local setup](#local-setup)) and in CI by `.github/workflows/conventions.yml`. A pull request that breaks them fails its checks.

### Commits: Conventional Commits

Every commit message and every PR title follows [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/#specification):

```
<type>[optional scope][!]: <description>

[optional body: why the change was made, wrapped at 72 characters]

[optional footer(s), e.g. BREAKING CHANGE: ..., Refs: #12]
```

- **Subject:** 72 characters or fewer, imperative mood, lowercase description, no trailing period.
- **Types:**

  | Type | For | SemVer effect |
  |---|---|---|
  | `feat` | new functionality | minor |
  | `fix` | bug fix | patch |
  | `docs` | documentation only | none |
  | `test` | adding or fixing tests | none |
  | `refactor` | code change that neither fixes a bug nor adds a feature | none |
  | `perf` | performance improvement | patch |
  | `build` | build system, dependencies | none |
  | `ci` | CI configuration | none |
  | `chore` | repository maintenance | none |
  | `style` | formatting only | none |
  | `revert` | reverts a previous commit | depends |

- **Scopes** (optional, lowercase): `data`, `policy`, `harness`, `classifiers`, `tools`, `ui`, `eval`, `agents`, `readme`, `deps`.
- **Breaking changes:** add `!` after the type or scope, and a `BREAKING CHANGE:` footer explaining the migration.
- **Examples:** `feat(policy): add two-threshold gate verdicts`, `fix(classifiers): fall back to rules when Laya times out`, `docs(readme): add usage examples`.

### Authorship

- Commits are authored and committed with the **maintainer's identity**: `Kevin Vicent <624602+moebious@users.noreply.github.com>`. Set it in the repository's local git config before committing.
- **Attribution:** the exact `Co-authored-by: factory-droid[bot] <138933559+factory-droid[bot]@users.noreply.github.com>` trailer is permitted only on commits whose changed paths are all Markdown (`.md`/`.mdx`). A single bootstrap commit modifying only `AGENTS.md`, `.githooks/commit-msg`, `.github/workflows/conventions.yml`, `scripts/git/check-commit-msg.sh`, `scripts/git/attribution-scope.sh` and `tests/git/test_git_rules.sh` may also carry that trailer. Other AI-tool co-authors, session links and generated-by footers remain prohibited on commits and PRs. The hook and CI compute scope from changed paths; a docs subject alone never grants an exception.
- **Agents never open pull requests.** After the maintainer approves a push, the agent gives the compare link (`https://github.com/moebious/factored-hackathon-2026-calvino/compare/main...<branch>?expand=1`) and a description following `.github/pull_request_template.md`; the maintainer opens the PR. PR-creation tools can append an attribution footer the agent cannot remove at creation.

### Branching

Never commit on `main`, locally or remotely: `main` changes only through merged pull requests. Every change starts on a short-lived branch (less than a day of work) from the latest `main`, in **its own worktree** (see below), named `<type>/<short-description>` with a Conventional Commits type, e.g. `feat/policy-gate`, `fix/laya-timeout`, `docs/data-contracts`. If a tool assigns a different branch name, use it and follow every other rule here.

### Worktrees: one per branch

Every branch is checked out in its own [git worktree](https://git-scm.com/docs/git-worktree), so branches never share a working directory, switching is instant, and parallel work (yours, or several coding agents') can't collide. The `main` checkout is read-only: it is only ever fast-forwarded, never committed to.

**Recommended layout (maintainer machines): bare repository**, after [Git worktree like a boss](https://dev.to/metal3d/git-worktree-like-a-boss-2j1b):

```bash
mkdir factored-hackathon-2026-calvino && cd factored-hackathon-2026-calvino
git clone --bare git@github.com:moebious/factored-hackathon-2026-calvino.git .bare
printf "gitdir: ./.bare" > .git
git config remote.origin.fetch "+refs/heads/*:refs/remotes/origin/*"
git fetch origin
git worktree add main                                         # read-only base
git worktree add feat-policy-gate -b feat/policy-gate origin/main
```

```
factored-hackathon-2026-calvino/
├── .bare/              git history, shared by every worktree
├── .git                file pointing to .bare
├── main/               main, only fast-forwarded
└── feat-policy-gate/   one directory per branch
```

**Existing clones and tool-provided checkouts:** keep the primary checkout on `main` and add worktrees under the git-ignored `.worktrees/` folder:

```bash
git worktree add .worktrees/policy-gate -b feat/policy-gate origin/main
```

Name the directory after the branch, with `/` replaced by `-` or without the type prefix.

**Lifecycle:**

```bash
git worktree list                         # what is checked out where
git worktree remove .worktrees/policy-gate   # after the PR is merged
git branch -d feat/policy-gate
git worktree prune                        # clean up after a directory was deleted by hand
```

Never delete a worktree with `rm -rf` alone; run `git worktree prune` afterwards, or use `git worktree remove`. A branch can only be checked out in one worktree at a time; git enforces this.

### Day-to-day commits

- **Plan the commits before writing code.** For a spec or task, first post the plan: an ordered list of the commits you intend to make, each one coherent change with its scope (for example: 1. dependencies and shared types; 2. adapter and fixture; 3. service and server; 4. docs). The maintainer can adjust it before any code exists. If the plan changes along the way, say so in the next report.
- **Prefer small logical commits.** One commit is one change a reviewer can read in a sitting, with the tests that belong to it. Don't fold several plan steps into one commit, and don't squash a finished branch into a single commit before pushing; the squash happens when the pull request is merged.
- **Size limits are enforced** by `scripts/git/check-commit-size.sh` in the `pre-push` hook and in CI: at most 15 files and 800 changed lines (added plus deleted) per commit, not counting lock files, `contracts/`, `tests/fixtures/` and `reports/`. A commit that really is one indivisible change (a rename across the tree, a generated file set) carries a footer `Size-exception: <reason>`, so the reason stays in the history. Splitting is the default; the exception is for when a split would leave a commit that does not build or pass its tests.
- **When you propose a push,** show the plan next to `git log --stat origin/main..HEAD`, so the maintainer can compare them.
- **Commit when one coherent change works,** with its tests passing. Never push a commit that breaks the build or the tests.
- **Fix mistakes with fixup commits,** then fold them in before pushing:
  ```bash
  git commit --fixup=<sha>
  GIT_SEQUENCE_EDITOR=: git rebase -i --autosquash origin/main   # non-interactive, safe for agents
  ```
  CI rejects any `fixup!` or `squash!` commit that reaches a pull request.
- **Keep your branch current by rebasing** onto `main`, never by merging `main` into it:
  ```bash
  git fetch origin && git rebase origin/main
  ```
- **Rewrite only your own, unmerged branch.** Never rebase or rewrite `main` or a branch someone else works on.
- **Push rewritten history with `--force-with-lease`, never `--force`,** so you can't overwrite work you haven't seen.

### Pushing: the maintainer decides

Coding agents never push on their own initiative. They commit locally and **push only when the maintainer explicitly approves that specific push**. "Push" covers anything that changes the remote: pushing commits, force-pushing or rewriting history, creating or deleting branches, pushing tags, and opening, updating, retargeting or closing pull requests. Approval for one push does not carry over to the next. When work is ready, the agent says what it would push, where, and why, and waits.

### Pull requests and merging

- Small, frequent pull requests into `main`: one topic, ideally less than a day of work.
- The **PR title is a Conventional Commits subject**, because it becomes the commit on `main`.
- Fill in `.github/pull_request_template.md`, keep tests passing, and add an entry to `CHANGELOG.md` under `Unreleased`.
- Merge with **squash and merge**; the squash commit message is the PR title. Delete the branch after merging.
- History on a shared branch is never rewritten. Tidy your own branch (reword, squash) before asking for review.

### Versioning and releases

[Semantic Versioning](https://semver.org), 0.x until submission. Milestones name planned capabilities; tag a milestone on `main` when it is actually reached and the maintainer approves a release. Do not backfill tags for unfinished or skipped milestones. T-502 packages the final submission changelog and optional approved final release; versioned policy, model and rubric promotion is governed separately by T-407/T-408.

| Version | Milestone |
|---|---|
| `v0.1.0` | design, decisions and repository standards |
| `v0.2.0` | data pipeline with contracts and quality checks |
| `v0.3.0` | Laya classifiers: baseline, calibration, evaluation |
| `v0.4.0` | LangGraph harness: Router, Gate, Verifier, human interrupts; minimal UI, deployed at a public link |
| `v0.5.0` | evaluation and governed thesis evidence |
| `v1.0.0` | hackathon submission |

### Signing (maintainer)

The maintainer signs commits and tags with an **SSH signing key** (`git config gpg.format ssh`, `user.signingkey`, `commit.gpgsign true`, `tag.gpgSign true`) so they show as Verified on GitHub. Squash merges done in the GitHub web interface are signed by GitHub. Coding-agent sessions cannot sign as the maintainer and leave signing off.

### Repository settings (maintainer)

Configured once on GitHub, listed here so they are not lost: squash merging only, defaulting to the PR title; automatically delete head branches; `main` protected with a ruleset (pull request required, `conventions` check required, no force pushes, no deletion); repository description, website and topics filled in. The `main-guard` workflow marks `main` red if a commit ever arrives without a merged pull request.

## Data and secrets

This repository is **public**.

- Never commit `data/`, `.env` files, credentials, API keys, model checkpoints or anything resembling customer records.
- Never write dataset bucket names, access keys or tokens into code, docs, tests or commit messages. Read credentials from environment variables.
- Test fixtures are small, synthetic and labelled as synthetic.
- Before pushing, scan the diff for secrets.

## Calvino design rules

These keep the system safe. Breaking one breaks the design, so raise it rather than working around it.

- **Probabilities in, deterministic verdicts out.** Laya returns probabilities; a versioned policy function decides. The same inputs and policy version always give the same verdict.
- **Hard rules run before Laya and always win** (fraud signals, amount limits, explicit requests for a human, etc.).
- **Thresholds live in the policy module,** never inline in hooks or prompts, and are unit tested.
- **Never gate on `action.act_probability`.** It carries no signal. Gate on calibrated probabilities and `confidence`.
- **The customer's session token never passes through a model.** The harness attaches it to tool calls, and tools check ownership.
- **Every decision is logged** to `decisions.jsonl` with its inputs, scores, rule fired and outcome.
- **New design decisions** get an entry in `docs/DECISIONS.md`.

## Evidence labels in docs

Tag factual claims in README and docs with their source: `[measured]` (we ran it), `[vendor]` (published by a model's author, not reproduced), `[read from chart]` (approximate), `[hypothesis]` (not yet tested).

## Commands

Keep these accurate; an agent should be able to run them as written. Run commands for the application will be added as it lands.

### Local setup

Run once per clone:

Use the worktree layout from [Worktrees](#worktrees-one-per-branch), then:

```bash
git config core.hooksPath .githooks                     # enable the commit-msg, pre-commit and pre-push hooks
git config user.name "Kevin Vicent"
git config user.email "624602+moebious@users.noreply.github.com"
```

The hooks enforce the rules above locally:

| Hook | Blocks |
|---|---|
| `pre-commit` | commits on `main`; commits from the primary checkout instead of a linked worktree; staged datasets, `.env` files, model weights and anything that looks like a credential |
| `commit-msg` | non-Conventional messages or AI-tool attribution outside the scoped Factory trailer on Markdown-only commits |
| `pre-push` | pushes to `main`; branch names that are not `<type>/<short-description>`; commits over the size limits, unless they carry a `Size-exception:` footer (all also checked in CI) |

Hooks can be skipped with `--no-verify`; don't. CI (`conventions`, `main-guard`) and branch protection catch what hooks miss.

### Python setup

Python 3.11 or newer and [uv](https://docs.astral.sh/uv/):

```bash
uv sync                             # create .venv with the package and dev tools from uv.lock
```

### Lint

```bash
uv run ruff check .                 # lint
uv run ruff format --check .        # formatting (uv run ruff format . to fix)
```

### Tests

```bash
uv run pytest                       # Python tests (no network, GPU or dataset needed)
bash tests/git/test_git_rules.sh    # git rule scripts and hooks
```

CI runs both on every pull request (`.github/workflows/tests.yml` and `conventions.yml`).

### Evaluation

```bash
uv run python scripts/run_evaluation.py --suite tier0            # offline: live laya (needs `uv pip install laya`), policy v3, TemplateAgent; no keys, no network
uv run python scripts/run_evaluation.py --suite all --repeats 3  # adds judge validation and the bare-LLM ablation when their keys are set
```

Writes `reports/eval/T-303-<date>-<git-sha>.md` (the human report) and `.json` (the machine results); both are committed. The gated parts skip with a named blocker when their environment variables are missing.

### Data contracts

```bash
uv run python scripts/validate_data_contracts.py --dir tests/fixtures/lakehouse   # audit a folder of tables (exit 1 on errors)
uv run python scripts/export_data_schemas.py                                      # regenerate contracts/data/ after changing the contracts
```

### Demo API and frontend

```bash
CALVINO_CONFIRMATION_KEY=<secret> uv run python -m calvino.api   # demo API on port 7860 (needs `uv pip install laya`; preloads at startup; endpoints are open, the hub needs a 32+-byte CALVINO_CONFIRMATION_KEY and stays off without it)
docker build -t calvino-demo:local .                            # the Space image (bakes the laya checkpoint; first build is several GB)
docker run -p 7860:7860 -v calvino-data:/data calvino-demo:local
cd frontend && npm install                                      # first time only
cd frontend && npm run lint && npm run build                    # frontend checks
cd frontend && BACKEND_URL=http://127.0.0.1:7860 npm run dev    # demo frontend on port 3000, /api/* rewritten to the backend
```

Deployment steps (Hugging Face Space, Vercel, `calvino.rubrica.dev`, keep-alive): [docs/DEPLOY.md](docs/DEPLOY.md).

### Language models

`providers.yaml` records which model answers each role; keys come from the environment and are
never committed. Check the deployment against it before a deploy:

```bash
uv run python scripts/check_providers.py               # also asks each provider what it serves (needs both keys)
uv run python scripts/check_providers.py --config-only # offline: only compares the environment with the file
```

The live check is deliberately not called at startup: a network call there would take the public
demo link down whenever a provider is briefly unavailable.
