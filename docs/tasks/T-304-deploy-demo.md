# T-304: Deploy the demo

| | |
|---|---|
| Wave | 3 |
| Branch | `build/deploy-demo` |
| Depends on | T-003, T-205, T-204 |
| Blocked by | hosting accounts (maintainer) |
| Model | standard model |
| Can run in parallel | yes |
| References | TSD-003; TSD-012 (spec); PRD NFR-5, NFR-8 |

**Goal.** Put the working system on `calvino.rubrica.dev`.

**Inputs.** the deployment skeleton; the maintainer's Space and Vercel projects and secrets

**Outputs.** a deployed backend and UI; keep-alive active; rate limit on (no passcode since decision 38); checkpoints and the decision log on persistent storage, with the restart test passing on the live Space

**Open parameters.** none

**Done when.** every scenario button works on the public link after a cold start

**Status.** Specified as [TSD-012](../specs/TSD-012-deploy-demo.md); code
complete on `build/deploy-demo`: the rate-limit identity fix
(`X-Forwarded-For` keying, raised limit for the judging window), the live
smoke check (`scripts/check_deployment.py`) with offline tests, and the
DEPLOY.md corrections. Remaining: the maintainer's live run per
[docs/DEPLOY.md](../DEPLOY.md) — accounts, secrets, domain, and a
smoke-check pass after a cold start.
