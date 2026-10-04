# TSD-012: Deploy the demo

| | |
|---|---|
| Status | implemented |
| Branch | `build/deploy-demo` |
| Depends on | TSD-003, TSD-009, TSD-010 |
| Required by | the evaluation (T-303), the video (T-504), the submission (T-505) |
| Requirements | PRD NFR-5, NFR-8 |
| Design | DESIGN.md decision 10; `docs/DEPLOY.md` |

## Purpose

Put the working system on `calvino.rubrica.dev` and keep it reachable through
the judging period. Most of the work is maintainer execution of
[docs/DEPLOY.md](../DEPLOY.md) (accounts, Space, Vercel, secrets, DNS); the
repository adds what DEPLOY.md cannot do by hand:

1. **A live smoke check** (`scripts/check_deployment.py`) that proves the
   card's "done when": every scenario button works on the public link after a
   cold start, with measured latencies and evidence labels.
2. **A rate-limit identity fix** (`calvino.api`): behind Vercel's rewrite
   every judge reaches the Space from the same egress IP, so keying the limit
   on the direct peer silently turns the per-client cap into a global one
   during judging. The limiter keys on the first `X-Forwarded-For` entry when
   the header is present, and the Space runs a raised limit for the judging
   window.
3. **DEPLOY.md corrections**: the stale `git push space build/deploy-skeleton:main`
   (push `main` instead), the raised judging-window rate limit, a "live smoke
   check" step after the domain section, and the measured cold-start numbers
   recorded once the Space exists.

## Interfaces

**Rate-limit identity (`calvino.api.app`)**

- The guard's client key becomes the first `X-Forwarded-For` entry when the
  header is present, else the direct peer. The comment says why (Vercel's
  rewrite proxies every judge from one IP) and names the trade-off: a client
  hitting the Space URL directly can spoof the header, which weakens the rate
  limit but never the passcode (NFR-8; decided in the TSD-012 review).
- Unit tests in `tests/calvino/api/`: header present keys on the first entry,
  absent keys on the peer, and a spoofed header changes only the limit, never
  authentication.

**`scripts/check_deployment.py`**

```bash
CALVINO_DEMO_PASSCODE=<passcode> uv run python scripts/check_deployment.py \
  --url https://calvino.rubrica.dev            # exit 0 only when every check passes
```

- The passcode is read from the environment, never from the CLI: it must not
  end up in shell history or a process listing.
- HTTP client: `httpx`, already a dev dependency (FastAPI's TestClient);
  `uv run` includes it, and the script stays out of the runtime image.
- Checks, in order:
  1. `GET /` (the frontend) returns 200 and contains the app title: the UI
     itself is served, not only the API rewrite.
  2. `GET /health` polled until 200 (the container wake on a cold Space;
     `--timeout` seconds, default 300; `--interval`, default 5), then
     `GET /ready` polled until true (the checkpoint preload). Both latencies
     and their total are the cold-start evidence. Neither endpoint is
     guarded, so the polls cost no rate-limit budget.
  3. `GET /api/hub/personas` returns the demo persona names.
  4. Each demo scenario — the same (persona, message, expected outcome)
     triples the frontend's scenario buttons send (`frontend/app/scenarios.ts`,
     mirrored as data in the script with a comment naming that file):
     a 200 with a card or a non-empty reply, and a non-empty trace.
  5. The approval scenario (dana, the retry message — UC-5) additionally
     parks: the reply carries `awaiting: approve_action` plus an
     `action_confirmation` card, and the resume with `decision: true` returns
     an `action_result` card.
  6. The operator-queue scenario (UC-4) parks with `awaiting: operator_queue`
     and resumes with a decision string.
- Budget: one full run costs about ten guarded requests (personas, seven
  scenario messages, two resumes) — comfortably inside the judging-window
  limit, but no rapid re-runs within a window.
- Output: one line per check with its latency `[measured]`, then a summary;
  exit 1 on any failure, printing expected versus received. The passcode is
  never printed.
- Not run in CI: it needs the live URL and the passcode. The maintainer runs
  it after every Space rebuild and after a restart (the cold-start proof).

**`docs/DEPLOY.md` changes**

- Step 2.2: push `main` to the Space (`git push space main`).
- Step 2.3: `CALVINO_DEMO_RATE_LIMIT` = 120 for the judging window (several
  judges share one apparent client behind the rewrite even with the
  `X-Forwarded-For` fix; the code default stays 30).
- A new step 7, "Live smoke check", with the command above and what it must
  print.
- After the first deployment: the measured time-to-ready after a Space
  restart, labelled `[measured]`.

## Behaviour

- The smoke check talks to the live demo only through its public endpoints.
  Its hub turns append decision records to the live log and park and resume
  real threads; that is acceptable because every datum behind them is the
  synthetic fixture, and it exercises exactly what a judge will do.
- Assertions are structural, not text equality: live Laya scores differ from
  the seeded test probabilities, so the script checks status codes, card keys,
  awaiting values and trace non-emptiness — never reply wording.
- Any non-2xx, a ready timeout, or a missing expected card fails the run;
  the script never retries a failed hub turn (a retry could double-fire a
  write; the Gate and the single-use tokens would catch it, but the check
  stays read-honest).

## Workflow context (decision 10)

One public origin, the UI as a verdict: the browser only ever talks to the
Vercel domain, which rewrites `/api/*`, `/health` and `/ready` to the Space.
NFR-5 (reachable through judging) is the keep-alive workflow from TSD-003
plus this task's cold-start evidence; NFR-8 (abuse protection) is the
passcode and rate limit already built, proven live by the smoke check's
guarded endpoints.

## Tests and acceptance

- Unit tests for the rate-limit key in `tests/calvino/api/` (no network, per
  the section above).
- Unit tests for the script in `tests/deployment/` (the `scripts/` ↔ `tests/`
  precedent; no network): the scenario table covers UC-1 to UC-5, UC-7 and
  UC-8 and includes the dana/retry approval flow; the check functions against
  a stubbed transport (success, health timeout, ready timeout, wrong card,
  missing passcode); the passcode never appears in argv or in the printed
  output; exit codes.
- Done when: `scripts/check_deployment.py --url https://calvino.rubrica.dev`
  exits 0 after a Space restart (cold start), the keep-alive workflow has run
  against the public URL, `decisions.jsonl` and `hub-checkpoints.sqlite`
  survive a restart on the live Space (DEPLOY.md's restart check), and the
  measured numbers are in DEPLOY.md with evidence labels.

## Blocked by

The maintainer's Hugging Face account and Space, the Vercel project, and DNS
access for `rubrica.dev` (HANDOFF next action 1). The script and the docs
land before the accounts exist; the live run happens the moment they do.
