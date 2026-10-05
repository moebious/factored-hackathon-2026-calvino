# T-307: Deployment Smoke-Check Verification and Persistence Testing

| | |
|---|---|
| Wave | 3 |
| Branch | `build/deploy-demo` |
| Spec | [TSD-012](../specs/TSD-012-deploy-demo.md), [TSD-025](../specs/TSD-025-durable-cases.md) |
| Depends on | T-304, T-306, T-401 |
| Blocked by | — |
| Model | standard model |
| Can run in parallel | yes |
| References | decisions 10, 38; PRD NFR-5, NFR-6, NFR-8; [docs/DEPLOY.md](../DEPLOY.md) |

**Goal.** Enhance `scripts/check_deployment.py` with a `--backend-only` flag to allow targeted backend verification, verify persistent storage mounting at `/data` on the Hugging Face Space, and validate case state survival across restarts (T-401).

**Context.**
Running `uv run python scripts/check_deployment.py --url https://kevago-calvino-laya.hf.space` executes 11 checks in ~5.2 seconds:
- 10 of 11 checks pass (`[ ok ]`): `/health` (95ms), `/ready` (124ms), `/api/hub/personas` (94ms), UC-1 to UC-3 (406–477ms), UC-4 operator queue (542ms), UC-5 approval action (559ms), UC-7/UC-8 (423–428ms).
- 1 check fails (`frontend served: FAIL got 404`) because `check_deployment.py` assumes the single origin serves both the Next.js HTML frontend at `/` and the API at `/api/*`. Since the backend Space serves only API endpoints, running against the backend directly currently exits 1.
- Additionally, state written during turns (`decisions.jsonl`, DuckDB cases) requires persistent storage attached at `/data` in Hugging Face Space settings to survive container restarts (T-401 durable-cases claim).

**Scope & Actions.**

1. **`check_deployment.py` CLI enhancement:**
   - Add `--backend-only` flag (skips the frontend root marker check).
   - When `--backend-only` is provided, evaluate only backend health, readiness, personas, and hub scenario turns (10 checks), exiting 0 when all 10 pass.
   - Maintain full 11-check default when testing the frontend/Vercel origin.

2. **Persistent Storage & Restart Survival (T-401 Verification):**
   - Ensure Space settings mount persistent storage at `/data`.
   - Run a stateful scenario turn (e.g. UC-5 confirmation or UC-4 case creation).
   - Restart the Space container.
   - Query the case reference to verify that DuckDB case state and `decisions.jsonl` survive the reboot.

3. **Full End-to-End Verification:**
   - Run `check_deployment.py --url <VERCEL_URL>` against the deployed frontend to obtain 11/11 passing checks with measured latencies.

**Done when.**
1. `check_deployment.py --backend-only --url https://kevago-calvino-laya.hf.space` exits 0 with 10/10 checks passing.
2. Unit tests in `tests/deployment/` cover the `--backend-only` flag without network access.
3. Case state survives a Space restart with `/data` mounted.
4. The full 11/11 suite passes against the Vercel frontend.
