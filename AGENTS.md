# AGENTS.md

Instructions for coding agents (and humans) working on this repository. Read this before making changes.

## Project

**Project Calvino** is an AI-first banking customer service system built around a domain-specific harness: a System One model (Laya) gives calibrated probabilities, a deterministic policy turns them into verdicts, an LLM handles only the language work, and humans step in where accountability is required.

- Design: [docs/DESIGN.md](docs/DESIGN.md)
- Decision log: [docs/DECISIONS.md](docs/DECISIONS.md)
- Build plan: [docs/PLAN.md](docs/PLAN.md)

## Repository layout

Planned. Directories are created as code lands; update this section when they do.

| Path | Contents |
|---|---|
| `src/calvino/` | Python package: harness (LangGraph graph), policy, classifiers (Laya), tools (MCP servers) |
| `frontend/` | CopilotKit / AG-UI client |
| `tests/` | Unit and integration tests, mirroring `src/calvino/` |
| `docs/` | Design, decisions, plan |
| `data/` | Local datasets. **Git-ignored, never committed** |

## Repository standards

1. **README.** It explains what the project does, why, and how to get it running. Whenever setup changes, update the run instructions in the same commit and make sure they still work.
2. **License.** The project is MIT-licensed (`LICENSE`). Don't add code or assets under incompatible licenses. Note third-party licenses where relevant (e.g. Laya is Apache 2.0).
3. **Clean repository.** Code, assets and config live in a sensible structure (see the layout above). Never commit OS files (`.DS_Store`, `Thumbs.db`), editor configs (`.vscode/`, `.idea/`), virtual environments, `node_modules/`, build artifacts, logs or model weights. `.editorconfig` is the only shared formatting config. If something unwanted shows up in `git status`, extend `.gitignore` instead of committing it.
4. **Clean history.** Each commit groups one coherent change and says so in its message. No "fix some things", "fix fixes" or revert chains: tidy work-in-progress commits locally before pushing.
5. **Comments.** Every file and class starts with a few lines saying what it does. Comment anything surprising: thresholds, workarounds, Laya quirks, deliberate trade-offs. Don't leave commented-out code.
6. **Tests.** Add or extend tests with every change. Every policy function and every tool permission check has unit tests that run without model calls. Tests must not need network access, a GPU or the real dataset.

## Git workflow

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
- **No AI-tool attribution** anywhere in the history or on pull requests: no `Co-Authored-By` trailers for tools, no session links, no "Generated with ..." lines in commit messages, PR titles or PR descriptions.

### Branching

Never commit on `main`: `main` changes only through merged pull requests. Every change starts on a short-lived branch (less than a day of work) from the latest `main`, named `<type>/<short-description>` with a Conventional Commits type, e.g. `feat/policy-gate`, `fix/laya-timeout`, `docs/data-contracts`. If a tool assigns a different branch name, use it and follow every other rule here.

### Pushing: the maintainer decides

Coding agents never push on their own initiative. They commit locally and **push only when the maintainer explicitly approves that specific push**. "Push" covers anything that changes the remote: pushing commits, force-pushing or rewriting history, creating or deleting branches, pushing tags, and opening, updating, retargeting or closing pull requests. Approval for one push does not carry over to the next. When work is ready, the agent says what it would push, where, and why, and waits.

### Pull requests and merging

- Small, frequent pull requests into `main`: one topic, ideally less than a day of work.
- The **PR title is a Conventional Commits subject**, because it becomes the commit on `main`.
- Fill in `.github/pull_request_template.md`, keep tests passing, and add an entry to `CHANGELOG.md` under `Unreleased`.
- Merge with **squash and merge**; the squash commit message is the PR title. Delete the branch after merging.
- History on a shared branch is never rewritten. Tidy your own branch (reword, squash) before asking for review.

### Versioning and releases

[Semantic Versioning](https://semver.org), 0.x until submission. Each milestone gets an annotated tag on `main` (`git tag -a v0.2.0 -m "..."`), the `Unreleased` changelog entries move under that version, and the tag is published as a GitHub Release with the changelog entry as release notes.

| Version | Milestone |
|---|---|
| `v0.1.0` | design, decisions and repository standards |
| `v0.2.0` | data pipeline with contracts and quality checks |
| `v0.3.0` | Laya classifiers: baseline, calibration, evaluation |
| `v0.4.0` | LangGraph harness: Router, Gate, Verifier, human interrupts; minimal UI, deployed at a public link |
| `v0.5.0` | evaluation and analytics |
| `v1.0.0` | hackathon submission |

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

To be filled in as tooling lands: setup, run, test, lint. Keep these accurate; an agent should be able to run them as written.
