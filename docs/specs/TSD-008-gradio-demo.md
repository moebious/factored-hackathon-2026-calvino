# TSD-008: Gradio demo deployment adapter

| | |
|---|---|
| Status | proposed |
| Branch | `feat/gradio-demo` |
| Task | [T-305](../tasks/T-305-gradio-demo-adapter.md) |
| Depends on | TSD-003, TSD-005 |
| Required by | public hackathon demo |
| Requirements | zero-cost public deployment; PRD NFR-5, NFR-8 |
| Design | deployment ADR in `docs/DECISIONS.md` |

## Purpose

Serve the TSD-005 demo decision path on a free Gradio SDK Space (zero hosting budget), while Docker/FastAPI (TSD-003) remains a supported production-shaped option. Gradio is a thin presentation/hosting layer: both adapters reuse the same Calvino core, so behavior stays identical and the Docker path can be restored without rewriting the model integration.

## Scope

In: root `app.py`, `requirements.txt`, Space metadata, parity tests, smoke test on a free Space, and the documentation updates below. Out: any change to `LayaClient`, calibration, policy or decision logic (TSD-005 stays closed); real labelled calibration, timeout handling, and hub/verifier integration, which are separate product tasks.

## Interfaces

**Gradio app** (root `app.py`):

```python
def decide(message: str, passcode: str):
    validate_passcode(passcode)
    return run_demo_decision(message, loader, policy, log)
```

- Preloads `LayaClient` at application startup, never on the first message.
- Accepts a message and a passcode; renders verdict, rule, scores and probabilities.
- Passcode validation stays server-side; `CALVINO_DEMO_PASSCODE` comes from a Space secret.
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

- Free Gradio Space is the live staging/hackathon demo; Docker/FastAPI remains functional as the production-shaped option, not a second implementation.
- Gradio state is explicitly ephemeral: sleeping/cold starts, `decisions.jsonl` may disappear after restart, no durable cases or checkpointer yet.
- No public API unless needed; no claim that the Docker deployment is live unless it has been deployed and tested.

## Smoke test

On a minimal private Gradio Space, verify before committing to this route: Python 3.11 is honored; `laya` and Torch install; the multilingual checkpoint fits memory; startup and inference finish within Space limits. If it fails, fall back to a recorded/local demo until hosting budget exists.

## Tests and acceptance

- Parity tests proving Gradio and FastAPI produce the same decision payload from the shared core.
- Passcode, preload and ephemerality behavior covered without model downloads where possible; live smoke test on the free Space.
- Existing lint and test suites pass.

**Done when** the decision payload matches across adapters, the smoke test passes on a free Space, Gradio state is documented as ephemeral, Docker/FastAPI still builds and serves locally, and the documentation updates below are merged.

## Documentation updates

Implementation updates `docs/DECISIONS.md` (one deployment entry: free Gradio Space for the demo, reason, scope, consequences, revisit trigger), `docs/DEPLOY.md`, `docs/HANDOFF.md`, the backlog, README and changelog, so no document keeps presenting Docker/Vercel as the active path.
