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

**Open parameters.** None structural; D1–D5 are proposed in TSD-021.

**Done when.** The premium demo runs all 7 scenarios ES/PT with green checks and `service.py` plus the smoke untouched (TSD-021 acceptance).

**First step:** spec written as TSD-021 (proposed), awaiting maintainer approval before implementing.
