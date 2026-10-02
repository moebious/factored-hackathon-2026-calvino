# TSD-000: Python scaffolding and shared types

| | |
|---|---|
| Status | draft |
| Branch | `build/python-scaffold` |
| Depends on | foundation PRs merged |
| Required by | TSD-001 to TSD-005 |
| Design | DESIGN.md 4.0.3 (components), 5 (governance) |

## Purpose

Create the Python project every other stream builds on, and fix the shared types early so parallel streams stay compatible. Keep it small: this PR merges before any other Wave 0 work starts.

## Scope

In: project configuration, package skeleton, shared types, decision log writer, CI test job, setup documentation. Out: any feature logic.

## Interfaces and data models

**Project:** `pyproject.toml`, Python 3.11+, `src/` layout, package `calvino`, managed with `uv`. Runtime dependency: `pydantic` v2. Dev: `pytest`, `ruff`.

**Package skeleton** (a short docstring per module; subpackages may be empty):

```
src/calvino/
  __init__.py
  records.py        shared types (below)
  policy/  tools/  verifier/  classifiers/  hub/
tests/              mirrors src/calvino/
```

**Shared types** in `calvino.records`:

| Type | Kind | Values or fields |
|---|---|---|
| `Route` | enum | `agents`, `human`, `out_of_scope` |
| `GateVerdict` | enum | `allow`, `ask`, `block` |
| `HumanAction` | enum | `none`, `approve_action`, `request_info`, `full_transfer` |
| `Stage` | enum | `hard_rules`, `classifier`, `gate`, `verifier`, `human` |
| `DecisionRecord` | pydantic model | `decision_id`, `timestamp`, `stage`, `session_ref` (a hash, never the token), `inputs_summary` (already redacted), `scores` (name → float), `rule_id` (optional), `policy_version`, `verdict`, `latency_ms`, `cost_usd`, `versions` (model, checkpoint, prompt, rubric) |

**Decision log:** an append-only JSONL writer for `DecisionRecord` (`decisions.jsonl`, git-ignored) and a reader that yields records back for replay.

## Tests and acceptance

- Schema tests: required fields, enum values, rejection of a raw session token in `session_ref`.
- Writer and reader round-trip.
- CI: `.github/workflows/tests.yml` runs `ruff` and `pytest` on pull requests.

**Done when** CI is green on the pull request and `uv run pytest` passes locally.

## Documentation updates

AGENTS.md: fill in the Commands section (setup, test, lint) and the repository layout for directories that now exist. README: setup instructions.
