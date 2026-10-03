# Deploying the demo

The exact steps for the maintainer to take the demo live at
`calvino.rubrica.dev` (TSD-003, decision 10): backend on a Hugging Face Space,
frontend on Vercel, one public origin. No secret ever enters the repository:
every key is a Space secret or a Vercel environment variable.

## 0. Prerequisites

- Docker locally, for the checks in [Local run](#1-local-run-verify-before-deploying).
- A Hugging Face account (the same one that will host Inference Providers,
  decision 20) and a Vercel account.
- Access to the DNS for `rubrica.dev`, for the CNAME record.

## 1. Local run (verify before deploying)

API only (needs laya locally: `uv pip install laya`; the unit tests never do):

```bash
CALVINO_DEMO_PASSCODE=<a-long-random-passcode> CALVINO_CONFIRMATION_KEY=<a-secret-of-32+-bytes> uv run python -m calvino.api
curl http://127.0.0.1:7860/health        # {"status":"ok"}
curl http://127.0.0.1:7860/ready         # {"ready":true} once the model is loaded
curl -X POST http://127.0.0.1:7860/api/demo/decide \
  -H 'content-type: application/json' -H 'x-calvino-passcode: <passcode>' \
  -d '{"text": "Mi transferencia sigue pendiente desde ayer."}'
curl -X POST http://127.0.0.1:7860/api/hub/message \
  -H 'content-type: application/json' -H 'x-calvino-passcode: <passcode>' \
  -d '{"persona": "ana", "text": "¿Por qué sigue pendiente E-MX-002?"}'
```

With Docker (matches the Space image; the first build downloads torch and the
laya checkpoint, several GB):

```bash
docker build -t calvino-demo:local .
docker run -p 7860:7860 -v calvino-data:/data calvino-demo:local
```

Frontend against the local backend:

```bash
cd frontend && npm install
BACKEND_URL=http://127.0.0.1:7860 npm run dev      # http://localhost:3000
```

The page shows the warm-up screen until `/ready` is true, then the demo form;
the result is the glass box (verdict, rule fired, scores, probabilities).

**Restart check** (state survives restarts, TSD-003 "done when"):

```bash
docker run -d --name calvino -p 7860:7860 -v calvino-data:/data \
  -e CALVINO_DEMO_PASSCODE=<passcode> -e CALVINO_CONFIRMATION_KEY=<key> calvino-demo:local
# send one decide request, then:
docker restart calvino
docker exec calvino cat /data/decisions.jsonl      # the record is still there
```

## 2. Hugging Face Space (backend)

1. New Space: name it (for example `calvino-demo`), SDK **Docker**, blank
   template, public (or private until the demo).
2. A Space is its own git remote. Push the branch (or `main`, once merged) to
   it; authenticating with your Hugging Face write token when asked:
   ```bash
   git remote add space https://huggingface.co/spaces/<user>/<space>
   git push space build/deploy-skeleton:main
   ```
   The Space rebuilds on every push. The checkpoint is baked into the image at
   build time, so the first build is slow (several GB of downloads) and every
   restart is fast.
3. Settings → Variables and secrets:

   | Name | Type | Value |
   |---|---|---|
   | `CALVINO_DEMO_PASSCODE` | secret | a long random string, e.g. `openssl rand -hex 24` |
   | `CALVINO_CONFIRMATION_KEY` | secret | a random string of at least 32 bytes, e.g. `openssl rand -hex 32`; without it the hub endpoints stay disabled (fail closed) |
   | `CALVINO_DEMO_RATE_LIMIT` | variable | optional; defaults to 30 per minute per client |

   `CALVINO_DATA_DIR` is already `/data` in the image; do not change it.
4. Settings → Persistent storage: enable it and make sure it mounts at
   `/data`. Without it, `decisions.jsonl` and later the hub's checkpoints are
   lost on every restart or rebuild. Note: on the free tier the persistent
   disk is detached while the Space sleeps, which is what the keep-alive ping
   prevents.
5. Wait for the build, then check `https://<user>-<space>.hf.space/health`
   and `/ready`.
6. No `HF_TOKEN` is needed: the laya checkpoint is public. Only add one if a
   gated model is pinned later.

## 3. Vercel (frontend)

1. New project: import the repository, **Root Directory** `frontend/`,
   framework preset Next.js.
2. Environment variables:

   | Name | Value |
   |---|---|
   | `BACKEND_URL` | `https://<user>-<space>.hf.space` (no trailing slash) |

3. Deploy. The project rewrites `/api/*`, `/health` and `/ready` to the
   backend, so the browser only ever talks to the Vercel domain.
4. Check: the site shows the warm-up screen, then the form; a decide request
   returns the glass box.

## 4. Custom domain `calvino.rubrica.dev`

1. Vercel → project → Settings → Domains: add `calvino.rubrica.dev`.
2. In the DNS for `rubrica.dev`, create the CNAME record Vercel shows
   (`cname.vercel-dns.com`).
3. Wait for the certificate, then re-check the demo through
   `https://calvino.rubrica.dev`.

## 5. Keep-alive

1. GitHub → repository → Settings → Secrets and variables → Actions →
   Variables: add `CALVINO_PUBLIC_URL` = `https://calvino.rubrica.dev` (or the
   Space URL until the domain exists).
2. The `keep-alive` workflow pings `/health` every 30 minutes
   (`.github/workflows/keep-alive.yml`). Until the variable exists it skips
   itself, so CI stays green while the accounts are being created.

## 6. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `/ready` false for minutes after a restart | Normal on a cold Space: the preload loads the checkpoint into memory (baked weights make this minutes, not a download). Watch the Space logs for errors. |
| `/api/demo/decide` returns 503 | `CALVINO_DEMO_PASSCODE` is not set: the endpoint fails closed until it is. |
| `/api/hub/*` returns 503 | the hub is disabled: `CALVINO_CONFIRMATION_KEY` is missing or shorter than 32 bytes, or the bundled bank fixture is unreadable. `/api/demo/decide` keeps working. |
| `/api/demo/decide` returns 403 | Wrong or missing `x-calvino-passcode` header. |
| 429 | Rate limit: wait for the `Retry-After` window or raise `CALVINO_DEMO_RATE_LIMIT`. |
| Frontend says "the demo backend is unreachable" | `BACKEND_URL` missing or wrong on Vercel; redeploy after fixing it. |
| Decisions gone after a restart | Persistent storage not enabled, or not mounted at `/data`. |
