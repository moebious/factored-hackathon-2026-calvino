# T-304: Deploy the demo

| | |
|---|---|
| Wave | 3 |
| Branch | `build/deploy-demo` |
| Depends on | T-003, T-205, T-204 |
| Blocked by | hosting accounts (maintainer) |
| Model | standard model |
| Can run in parallel | yes |
| References | TSD-003; PRD NFR-5, NFR-8 |

**Goal.** Put the working system on `calvino.rubrica.dev`.

**Inputs.** the deployment skeleton; the maintainer's Space and Vercel projects and secrets

**Outputs.** a deployed backend and UI; keep-alive active; passcode and rate limit on

**Open parameters.** none

**Done when.** every scenario button works on the public link after a cold start

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
