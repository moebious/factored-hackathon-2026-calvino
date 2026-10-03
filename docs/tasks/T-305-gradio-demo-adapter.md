# T-305: Gradio demo adapter (free hosted demo)

| | |
|---|---|
| Wave | 3 |
| Branch | `build/gradio-demo` |
| Depends on | T-005 (merged) |
| Blocked by | free Hugging Face Space (maintainer creates) |
| Model | standard model |
| Can run in parallel | yes |
| References | TSD-003 (Docker/FastAPI retained as the production-shaped option); PRD NFR-5, NFR-8 |

**Goal.** Serve the TSD-005 demo decision path on a free Gradio SDK Space, keeping the Docker/FastAPI deployment as the production-shaped option. Presentation/hosting adapter only: `LayaClient`, the policy, `run_demo_decision()`, schemas and tests stay shared and framework-independent.

**Not in scope.** TSD-005 stays closed (Laya client and calibration are done). Real labelled calibration (T-106 set), timeout handling, and hub/verifier integration are separate product tasks and must not reopen this card.

**Inputs.** the merged `calvino.classifiers` and policy; a minimal private Gradio Space for the smoke test.

**Outputs.** root `app.py` (preload `LayaClient` at startup; accept message and passcode; call `run_demo_decision()`; render verdict, rule, scores, probabilities); `requirements.txt` with a pinned `laya`; Space metadata in `README.md` (`sdk: gradio`, `app_file: app.py`, `python_version: "3.11"`); `CALVINO_DEMO_PASSCODE` as a Space secret; decision entry (next number) in `docs/DECISIONS.md`; updates to `docs/DEPLOY.md`, `docs/HANDOFF.md`, the changelog and this backlog row.

**Open parameters.** whether the Gradio function needs an `api_name` (only if an external frontend must call it; otherwise use the Gradio UI directly and drop Vercel for now).

**Done when.**
- `app.py` calls the existing `run_demo_decision()` core; Laya preloads at startup, never on the first message.
- Python 3.11 and dependencies install on the Space; the multilingual checkpoint fits memory and inference finishes within Space limits.
- Passcode validation is server-side in both adapters; no public API unless needed.
- Parity tests prove Gradio and FastAPI produce the same decision payload.
- Ephemeral persistence and cold-start limitations are documented (sleeping Spaces, `decisions.jsonl` may disappear, no durable cases yet); Docker/FastAPI remains functional.
- Gradio deployment is smoke-tested on a free Space; existing lint and test suites pass.

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
