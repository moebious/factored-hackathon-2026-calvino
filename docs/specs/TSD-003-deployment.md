# TSD-003: Deployment skeleton

| | |
|---|---|
| Status | draft |
| Branch | `build/deploy-skeleton` |
| Depends on | TSD-000 |
| Required by | the demo link (Wave 3 gate) |
| Requirements | PRD NFR-5, NFR-8 |
| Design | DESIGN.md 4.0.2; decision 10 |

## Purpose

Make the deployment path real before the features exist, so every later PR can be seen on the public link and problems surface early.

## Interfaces

**Backend** (`calvino.api`, FastAPI):

| Endpoint | Behaviour |
|---|---|
| `GET /health` | process is up |
| `GET /ready` | true once Laya is loaded |
| `POST /api/demo/decide` | runs one Laya decision on a short text (passcode required) |

**Hugging Face Space:** a Dockerfile (port 7860, non-root user) that installs the package and downloads the `laya-multilingual` checkpoint at build time, so restarts don't re-download. Laya is preloaded at startup, never on the first request.

**Frontend:** a minimal Next.js app in `frontend/`, with a rewrite of `/api/*` to the backend URL from an environment variable, and a warm-up screen that polls `/ready`.

**Keep-alive:** a scheduled GitHub Actions workflow that requests the public URL, stored as a repository variable, not hard-coded.

## Behaviour

- Demo passcode and a simple rate limit on the API.
- No secrets in the repository; all keys come from Space secrets and Vercel environment variables.

## Tests and acceptance

- API tests with a fake Laya.
- Documented local run: `docker build` and `docker run` serve `/ready` and the demo endpoint; the frontend shows the warm-up screen, then the result, against the local backend.

**Done when** the local end-to-end run works, and `docs/DEPLOY.md` lists the exact maintainer steps: Space secrets, Vercel project and environment variables, and the CNAME record for `calvino.rubrica.dev`.
