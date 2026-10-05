# Frontend roadmap: phases F1–F3 plus the FE-1 lane

*The order of record for frontend work, transcribed from the team
checklist (Roadmap UI Calvino). The interactive page
[roadmap-checklist.html](roadmap-checklist.html) mirrors this file; what
merges here overrules its browser checkboxes. Status moves in the pull
request that completes each phase — never in a separate sync, never only
in a browser checkbox. Parent backlog rows: T-207 (Fases 1–2), T-208
(Fase 3), T-304 (F1.5 live deploy). When a phase completes, its PR
updates this file plus its parent card row per docs/tasks/README.md.*

Status: `done`, `review` (pushed, awaiting evidence or merge),
`doing`, `todo`.

## Fase 1 — open and found

Exit: pytest + git rules + lint/build green · 7 scenarios OK · smoke
green · spec merged.

| ID | Task | Depends on | Verify | Status |
|---|---|---|---|---|
| F1.1 | Remove backend passcode | — | pytest + ruff | done (#68) |
| F1.2 | Passcode-free scripts (check_deployment + tests) | F1.1 | pytest deploy | done (#68) |
| F1.3 | Passcode-free frontend | F1.1 | lint/build | done (#68) |
| F1.4 | Open-demo docs (DECISIONS, NFR-8, README, AGENTS, DEPLOY…) | F1.1–F1.3 | review | done (#68) |
| F1.5 | Live deploy + smoke (maintainer) — EARLY INDEPENDENT TRACK — STAND BY pending deploy | — (deploy outranks F1.7–F1.10) | green smoke | todo (T-304; on standby until the deploy unblocks) |
| F1.6 | Restack 8604f55 into compliant commits (premium shell) | F1.1 | hooks + CI | done (#71) |
| F1.7 | Hygiene: drop ai dep + attachments, i18n FR-13 | F1.6 | lint/build | todo |
| F1.8 | Conversation reducer (friction 6) | F1.6 | build + scenarios | todo |
| F1.9 | vocabulary.ts with raw fallback (friction 3) | F1.6 | build | todo |
| F1.10 | TSD-021 premium spec, proposed | write now | review | todo (awaiting approval) |

## Fase 2 — premium experience, zero backend

Exit: navigable ES/PT demo without touching service.py or the smoke.

| ID | Task | Depends on | Verify | Status |
|---|---|---|---|---|
| F2.1 | CaseStudy dossier + case timeline | F1.8, F1.9, F1.10 | build + scenarios | todo |
| F2.2 | Adaptive input (ported registry + decide(), mode C) | F1.10, F1.7 | manual typing | todo (composer shell + regex morphs exist from #71; specified registry+decide port pending) |
| F2.3 | Dynamic cards + queued-case panel (frictions 1, 2a) | F2.1, F2.2 | UC-4/UC-5 | todo |
| F2.4 | Faithful ChainOfThought from the real source (D1c) | F1.9 | build + trace | todo (local adapter rendering trace exists; real-source port per D1 pending) |
| F2.5 | Glassbox with labels + bars vs threshold | F1.9 | build | todo |
| F2.6 | Choreographed Nivel A with honest copy | F2.1–F2.5 | manual demo | todo |

## Fase 3 — Laya as Jev + closeout, conditional

Exit: live demo with or without the endpoint per measurement. If Q1
fails: F3.2+F3.3+F3.5+F3.6.

| ID | Task | Depends on | Verify | Status |
|---|---|---|---|---|
| F3.0a | Q1 Space latency (GO if p95 ≤800 ms) | T-304 (needs the live Space) | measurement | todo (blocked until the Space is live) |
| F3.0b | Q2 PT probe (GO if comparable to ES) | — (local Laya install; no live Space needed) | measurement | todo |
| F3.1 | POST /api/composer/intent + dedicated pool | Q1/Q2 GO + F2.2 | offline pytest | todo |
| F3.2 | Expose turn intent (same wave) | Fase 2 output | pytest + build | todo |
| F3.3 | policy_version in TraceStep (same wave) | F3.1/F3.2 | pytest + build | todo |
| F3.4 | Optional SSE spike (Nivel B only if validated) | F2.6 | spike | todo |
| F3.5 | v3 runbook + contingent retuning | — | docs | todo |
| F3.6 | Closeout: full verification, docs, deploy, smoke | F3.1–F3.5 | all green | todo |

## FE-1 lane — 5 frontend PRs, parallel

One PR per task plus a CHANGELOG second commit each. Order: PR-1 →
PR-4 → PR-2 → PR-3 → PR-5. FE-1 is not a backlog card: coordinate,
don't duplicate.

| ID | Task | Depends on | Verify | Status |
|---|---|---|---|---|
| PR-1 | Local voice (feat/voice-input) | — | lint/build + matrix | review (pushed unmerged, remote branch deleted, work preserved locally; lint/build evidence pending) |
| PR-4 | Safe traceability (c438b65 + 4-line i18n fix) | — | lint/build | todo |
| PR-2 | Local case (re-resolved after voice merge) | PR-1 merge | lint/build | todo |
| PR-3 | Intent-card (after PR-2 merge) | PR-2 merge | lint/build | todo |
| PR-5 | Stop voice on send (after PR-2) | PR-2 merge | lint/build | todo |

Constraint: the future FE-1 proposal file may NOT be named
intent-driven-card.tsx (taken by the composer since PR #71).

## Non-negotiable invariants (all phases)

1. Fixed FR-7 catalog plus a named fallback card; an unknown key never crashes.
2. The glass box reads only `HubReply.trace`; no private model reasoning ever renders.
3. No free text on screen: i18n chrome or verified payload fields only.
4. Confirm / deny resume the exact parked action (`awaiting_ref`); a denial escalates.
5. ES / PT toggle translates chrome only; hub replies pass through untouched.
6. The session token never reaches the frontend.
7. Thresholds live only in `policy/`; the UI reads them from `summary.threshold`.
8. Policy-agnostic presentation: `vocabulary.ts` registry with raw-key fallback,
   open unions in `types.ts`, new rule/route ids render without type edits.

## Approved decisions D1–D5

- D1c: port the real Chain-of-Thought source to React 18 + plain CSS; local
  adapters for the rest; full React 19 + Tailwind migration deferred post-hackathon.
- D2: drop local attachments (a shown-but-unprocessed file is dishonest UI).
- D3: choreographed Nivel A first; real SSE Nivel B only on a validated spike.
- D4: restack the premium branch into compliant commits (done, #71).
- D5: port Shapeshift's `decide()` + intent registry with no online Jev; Laya
  becomes the source later via the composer endpoint (GO-conditional, see gates).

## Q1 / Q2 gates (pre-committed, mechanical)

- Q1 Space latency: p95 of the composer question set on the Space. GO if
  <= 800 ms; fallback to mode C (existing scores) if > 1500 ms; grey zone
  800–1500 ms ships with 500 ms debounce, aggressive cache and re-measurement.
- Q2 Portuguese probe: GO bilingual if PT confidences are healthy and comparable
  to ES; else Laya morph ES-only with keyword fallback in PT (same graceful
  pattern as SpeechInput).
- If Q1 fails, Fase 3 contracts to F3.2 + F3.3 + F3.5 + F3.6.

## Numbering rule (lesson from TSD-018/019/020)

Spec numbers are claimed by merge order: before opening a spec PR, re-check
`docs/specs/README.md` on current `main` and renumber if your number was taken.
