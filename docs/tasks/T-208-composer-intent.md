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

**Phases.** Order of record: [frontend-roadmap.md](frontend-roadmap.md) (Fase 3); the list below summarizes it.
- F3.0a Q1 latency on the Space (GO if p95 ≤800 ms; fallback C if >1500 ms; intermediate with 500 ms debounce) — measurable now.
- F3.0b Q2 PT probe (GO if comparable to ES; else Laya ES-only + keywords in PT) — measurable now.
- F3.1 POST /api/composer/intent + dedicated pool + no-log note — needs Q1/Q2 GO + F2.2.
- F3.2 expose turn intent (same wave) — needs Fase 2 output.
- F3.3 policy_version in TraceStep (same wave) — needs F3.1/F3.2.
- F3.4 SSE spike, optional (Nivel B only if validated) — needs F2.6.
- F3.5 v3 runbook + contingent retuning — docs only, no dependencies.
- F3.6 full verification + docs + deploy + smoke — needs F3.1–F3.5.
If Q1 fails, Fase 3 = F3.2+F3.3+F3.5+F3.6 (C already comes in F2.2).

**Open parameters.** Debounce within 300–500 ms, set by Q1.

**Done when.** Endpoint pytest offline green, probes meet their pre-committed thresholds (or the documented fallback ships), smoke unaffected.

**First step:** run the Q1/Q2 probes; implement the endpoint only on GO.
