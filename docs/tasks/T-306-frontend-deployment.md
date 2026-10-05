# T-306: Frontend Deployment and Live Interface Execution

| | |
|---|---|
| Wave | 3 |
| Branch | `build/deploy-demo` |
| Spec | [TSD-012](../specs/TSD-012-deploy-demo.md) |
| Depends on | T-205, T-207, T-304 |
| Blocked by | Vercel deployment / maintainer run |
| Model | standard model |
| Can run in parallel | yes |
| References | decisions 10, 38; PRD NFR-5, NFR-8; [docs/DEPLOY.md](../DEPLOY.md) |

**Goal.** Deploy and verify the interactive Next.js customer application and operator console against the live Hugging Face Space backend (`https://kevago-calvino-laya.hf.space`).

**Context.** 
- **Backend (FastAPI on Hugging Face Spaces):** Live at `https://kevago-calvino-laya.hf.space`. Serves the deterministic cognitive hierarchy (System 1 Laya perception, System 1.5 policy engine, ISO 20022 banking data, and verifier cascade). Root `/` returns `{"detail":"Not Found"}` by design; interactive API docs are served at `/docs`, with `/health` and `/ready` probes.
- **Frontend (Next.js in `frontend/`):** Hosts the customer glass-box experience, scenario picker buttons, intent-driven cards, voice recognition, and the System 3 Operator Console (`/console`).

**Execution Modes.**

1. **Live Production Deployment (Vercel):**
   - Import repository to Vercel.
   - **Root Directory:** `frontend/` (Framework preset: Next.js).
   - **Environment Variable:** `BACKEND_URL=https://kevago-calvino-laya.hf.space` (no trailing slash).
   - Domain: `calvino.rubrica.dev` (or default `*.vercel.app`).

2. **Local Live Run (Development against Live Space):**
   ```bash
   cd frontend
   BACKEND_URL=https://kevago-calvino-laya.hf.space npm run dev
   # Opens http://localhost:3000
   ```

**Outputs.**
- Deployed frontend origin with transparent `/api/*` rewrites to the Hugging Face Space.
- Cold-start warm-up screen tied to backend `/ready`.
- Fully interactive customer chat and operator workspace (`/console`).

**Done when.**
1. `npm run build` inside `frontend/` succeeds with 0 errors.
2. Vercel deployment is live and reachable over HTTPS.
3. Visiting the frontend root `/` loads the Calvino UI and connects to the backend without CORS or rewrite errors.
4. `uv run python scripts/check_deployment.py --url <DEPLOYED_URL>` passes 100% of checks across all scenario buttons and approval workflows.
