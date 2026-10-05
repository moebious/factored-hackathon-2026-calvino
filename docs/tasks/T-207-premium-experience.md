# T-207: Premium customer experience

| | |
|---|---|
| Wave | 2 |
| Branch | `feat/premium-shell` (F1.6 restack merged in #71) then per-phase branches |
| Depends on | T-205 |
| Blocked by | — |
| Model | standard model |
| Can run in parallel | yes |
| References | TSD-021 (proposed); PRD FR-7, FR-12, FR-13; decisions 10, D1–D5 (proposed) |

**Goal.** Turn the TSD-010 screen into a visual investigation in progress: a client-side `CaseStudy` dossier, an adaptive input (registry + `decide()` ported, source-agnostic `IntentResult`), choreographed Nivel A progress. No backend change in Fase 2.

**Inputs.** The frozen `HubReply` contract; Shapeshift registry/`decide()` patterns (MIT, attribution kept); the F1.6 restack (merged in #71).

**Outputs.** F1.6–F1.9 foundation (restack, hygiene, reducer, vocabulary) plus F2.1–F2.6 (dossier, adaptive input, dynamic cards, faithful Chain of Thought, glass-box labels, Nivel A), all ES/PT with the 7 scenarios green.

**Phases.** Prior context (merged via #68, informational): F1.1–F1.4 open demo. F1.5 deploy+smoke lives in T-304 (nothing to do here).
- F1.6 premium shell restack — merged (9b82826, PR #71). Done.
- F1.7 hygiene (drop ai dep + attachments, i18n FR-13) — needs merged F1.6.
- F1.8 conversation reducer (friction 6) — needs F1.6.
- F1.9 vocabulary.ts with raw fallback (friction 3, policy-agnostic) — needs F1.6.
- F2.1 CaseStudy dossier + timeline — needs F1.8, F1.9.
- F2.2 adaptive input (ported registry + decide(), keywords source + mode C) — needs TSD-021 spec.
- F2.3 dynamic cards + queued-case panel (frictions 1, 2a) — needs F2.1, F2.2.
- F2.4 faithful Chain of Thought (D1c, trace only) — needs F1.9.
- F2.5 glass-box labels + bars vs summary.threshold — needs F1.9.
- F2.6 choreographed Nivel A, honest copy — needs F2.1–F2.5.
- Parallel lane FE-1 (not registered as a card; coordinate, don't duplicate): PR-1 voice pushed unmerged (remote branch deleted, work preserved locally); order PR-4 → PR-2 → PR-3 → PR-5; the future FE-1 proposal file may NOT be named intent-driven-card.tsx (taken by the composer since PR #71).
Per-phase done-when: green lint/build + 7 ES/PT scenarios where applicable; Fase 2 without touching service.py or the smoke.

**Open parameters.** None structural; D1–D5 are proposed in TSD-021.

**Done when.** The premium demo runs all 7 scenarios ES/PT with green checks and `service.py` plus the smoke untouched (TSD-021 acceptance).

**First step:** spec written as TSD-021 (proposed), awaiting maintainer approval before implementing.
