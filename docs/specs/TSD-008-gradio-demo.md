# TSD-008: Gradio demo deployment adapter

| | |
|---|---|
| Status | proposed emergency diagnostic fallback only (decision 37) |
| Branch | `feat/gradio-demo` |
| Task | [T-305](../tasks/T-305-gradio-demo-adapter.md) |
| Depends on | TSD-003, TSD-005 |
| Required by | public hackathon demo |
| Requirements | zero-cost public deployment; PRD NFR-5, NFR-8 |
| Design | deployment ADR in `docs/DECISIONS.md` |

## Purpose

Serve the TSD-005 demo **decision-only** path on a free Gradio SDK Space if the full hub and Next.js app cannot be publicly hosted. Docker/FastAPI (TSD-003) remains the supported full-product option. Gradio is a thin presentation/hosting layer for System 1/1.5 diagnostics; it cannot be counted as T-304 completion or as evidence of the verifier, action and operator-handoff journey.

## Scope

In: root `app.py`, `requirements.txt`, Space metadata, parity tests, smoke test on a free Space, and the documentation updates below. Out: any change to `LayaClient`, calibration, policy or decision logic (TSD-005 stays closed); real labelled calibration, timeout handling, and hub/verifier integration, which are separate product tasks.

## Interfaces

**Gradio app** (root `app.py`):

```python
def decide(message: str):
    return run_demo_decision(message, loader, policy, log)
```

- Preloads `LayaClient` at application startup, never on the first message.
- Accepts a message; renders verdict, rule, scores and probabilities.
- An `api_name` is exposed only if an external frontend must call it; otherwise the Gradio UI is the demo and Vercel is dropped for now.

**Dependencies:** `requirements.txt` with the runtime dependencies, including a pinned, compatible `laya` version.

**Space metadata** in `README.md`:

```yaml
---
title: Calvino
sdk: gradio
app_file: app.py
python_version: "3.11"
---
```

## Behaviour

- A free Gradio Space is an explicitly labelled emergency diagnostic fallback; Docker/FastAPI and the Next.js app remain the full-product path, not a second decision implementation.
- Gradio state is explicitly ephemeral: sleeping/cold starts, `decisions.jsonl` may disappear after restart, no durable cases or checkpointer yet.
- No public API unless needed; no claim that the Docker deployment is live unless it has been deployed and tested.

## Smoke test

On a minimal private Gradio Space, verify before committing to this route: Python 3.11 is honored; `laya` and Torch install; the multilingual checkpoint fits memory; startup and inference finish within Space limits. If it fails, fall back to a recorded/local demo until hosting budget exists.

## Tests and acceptance

- Parity tests proving Gradio and FastAPI produce the same decision payload from the shared core.
- Rate limit, preload and ephemerality behavior covered without model downloads where possible; live smoke test on the free Space.
- Existing lint and test suites pass.

**Done when** the decision payload matches across adapters, the smoke test passes on a free Space, Gradio state is documented as ephemeral, Docker/FastAPI still builds and serves locally, and every public description distinguishes this fallback from the full hub and customer app.

## Documentation updates

If this fallback is activated, update `docs/DEPLOY.md`, `docs/HANDOFF.md`, the backlog, README and changelog to name **which** path is actually live and what the fallback cannot demonstrate. Decision 27 records the original hosting rationale; decision 37 restricts its role. Do not claim Docker/Vercel is live until it passes T-304.
