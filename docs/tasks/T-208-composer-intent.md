# T-208: Composer intent endpoint (Laya as the composer Jev)

| | |
|---|---|
| Wave | 3 |
| Branch | `feat/composer-intent` (planned) |
| Depends on | T-207 |
| Blocked by | Q1/Q2 probe GO verdicts (pre-committed thresholds in TSD-021) |
| Model | standard model |
| Can run in parallel | yes |
| References | TSD-021 §endpoint (proposed); D5 GO-conditional |

**Goal.** A debounced, text-only intent endpoint feeding the client's source-agnostic `IntentResult`: dedicated rate pool, LRU cache, no decision logging. Plus the Q1/Q2 probes and the v3 policy runbook.

**Inputs.** `loader.classify` with the existing question builders; the live Space for Q1.

**Outputs.** `POST /api/composer/intent` (composer-v1), probe briefs `docs/research/q1-*.md` and `q2-*.md`, the DEPLOY runbook section. Fallback C (mode scores) if Q1 fails.

**Open parameters.** Debounce within 300–500 ms, set by Q1.

**Done when.** Endpoint pytest offline green, probes meet their pre-committed thresholds (or the documented fallback ships), smoke unaffected.

**First step:** run the Q1/Q2 probes; implement the endpoint only on GO.
