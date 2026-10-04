# TSD-021: Premium conversational customer experience

| | |
|---|---|
| Status | proposed |
| Branch | `feat/premium-experience` (phased: F2, then F3) |
| Depends on | TSD-009 (hub), TSD-010 (customer app and card catalog) |
| Required by | the demo link (judges see a visual investigation, not a form) |
| Requirements | PRD FR-7, FR-8, FR-12, FR-13; UC-1 to UC-5, UC-7, UC-8 |
| Design | DESIGN.md 2, 6; decisions 10, 17 (proposes follow-ups, registers none) |

## Purpose

Turn the TSD-010 customer screen into a premium conversational experience: the
user writes or speaks a request, watches the request become a case study, sees
cards accumulate as verified backend data arrives, follows an auditable trail of
completed steps, and receives a final answer grounded only in verified tool
results. The experience must feel like a visual investigation in progress, not a
traditional form.

This spec extends TSD-010; it does not replace it. The hub contract, the card
catalog and the glass-box rule stay exactly as specified there until the
contract wave (F3.2/F3.3) lands, and every change in this spec keeps the demo
working at each phase against the current contract.

Three layers, in one spec because none ships alone:

1. **A client-side case study (`CaseStudy`)** aggregating the thread: intent
   preview, accumulated cards, evidence, pending action, trace and final
   response. No backend change; the dossier is derived from `HubReply`.
2. **An adaptive input** (registry + `decide()` ported from Shapeshift, MIT):
   ghost / choose / committed presentation with hysteresis, driven by an
   `IntentResult` agnostic to its source (keywords first, Laya later).
3. **Choreographed progress (Nivel A now, Nivel B SSE only if the spike
   validates it)** plus a dedicated `POST /api/composer/intent` endpoint
   (composer-v1) so Laya can replace keywords as the intent source in Fase 3.

The language work stays deterministic until T-301 lands the LLM agent: no
free-form generation on screen, decision 10 unchanged.

## Non-negotiable invariants

These survive every phase; a proposal that breaks one is rejected, not worked
around:

1. **Fixed catalog (FR-7).** Only the TSD-010 keys render; an unknown key
   renders the named fallback card, never a crash, never generated markup.
2. **The glass box reads only the trace.** The panel (and the Chain of Thought
   built from it) shows stage, rule, verdict, scores and summary from
   `HubReply.trace` and nothing else. No private model reasoning ever renders.
3. **No free text on screen.** Every sentence is a chrome string (i18n) or a
   verified payload field. Replies come from the hub; labels come from
   `vocabulary.ts` or the raw key as fallback.
4. **Confirm / deny hit the exact parked action.** The buttons resume with the
   turn's own `awaiting_ref` and disable while the request is in flight; a
   denial escalates to a person, as today.
5. **i18n covers chrome only (FR-13).** The ES / PT toggle translates UI
   strings; customer data and hub replies pass through untouched.
6. **The session token never reaches the frontend.** Authentication and session
   attachment stay server-side, as today.
7. **Thresholds live only in `policy/`.** The frontend never hardcodes a
   cutoff; any number it displays comes from `summary.threshold` in the trace.

## Interfaces and data models

### CaseStudy (client-side aggregation)

```text
CaseStudy
- id: string             # client-generated; reuses case_ref when the hub opens one
- title: string          # chrome-derived (persona + first intent label), never model text
- status: CaseStatus     # derived machine, see below; no backend field today
- intent: IntentPreview | null   # preview layer (client) + authoritative layer (route)
- input: { text: string, voice: boolean }  # message exists; voice flags transcription
- cards: CardInstance[]  # accumulated across turns; several per turn allowed
- evidence: EvidenceRef[]         # partial today (cards + trace summaries); rich needs T-H
- pendingAction: { awaiting, awaiting_ref } | null  # exists as HubReply fields
- trace: TraceStep[]     # exists; concatenated across the thread in order
- finalResponse: string | null   # exists as HubReply.reply
```

`CaseStatus`: `draft → sent → answered | awaiting | queued | refused | escalated | error`.

- `draft`: text in the composer, not yet sent.
- `sent`: turn pending, request in flight.
- `answered`: a reply arrived with no park and no escalation.
- `awaiting`: the reply carries `awaiting: "approve_action"` (confirm / deny
  shown, bound to `awaiting_ref`).
- `queued`: the reply carries `awaiting: "operator_queue"` (operator decision
  field shown).
- `refused`: the reply carries the `refusal` card.
- `escalated`: the reply carries `escalated: true`.
- `error`: transport or contract failure (see Behaviour).

Client-side vs contract, field by field: `id` (client until `case_ref`
exists), `title` (client), `status` (client derivation), `intent.preview`
(client), `intent.route` (contract `route`), `input.text` (contract `message`),
`cards` (contract `card`, accumulated), `evidence` (partial: contract-derived),
`pendingAction` (contract `awaiting` + `awaiting_ref`), `trace` (contract),
`finalResponse` (contract `reply`). The rich version (multi-card per turn,
full evidence, server intent) is the contract wave T-H, not this spec's Fase 2.

### intent in two layers

- **Preview (client, non-authoritative):** `IntentResult` from the adaptive
  input (keywords in Fase 2, Laya via composer endpoint in Fase 3). Drives only
  presentation: ghost hint, choose disambiguation, committed preview card.
- **Authoritative (server):** `HubReply.route`, set by Laya + policy. This is
  the only intent the dossier records as decided.

The preview never writes to the dossier, never fires a tool, never logs a
decision.

### Adaptive input: registry + decide() (ported, no new dependency)

Port Shapeshift's `registry.ts` + `decide.ts` patterns (MIT, attribution kept)
with banking intents; do not install the package (React 19 + Tailwind v4 +
shadcn + Bun are incompatible with the current React 18 + plain-CSS frontend).

- **Registry:** one entry per composer intent: label, example, icon, signals
  (weighted keywords ES/PT), badges, header icon, summary, preview component.
- **`decide()`:** calm-UI state machine `input | ghost | choose | committed`
  with hysteresis (inputBelow, commitAt, chooseGap, chooseFloor,
  challengerOverride, challengerWins, dropBelow — values tuned in
  implementation, never in `policy/` since they gate presentation, not
  verdicts). Forced-text match via levenshtein, as upstream.
- **`IntentResult` (source-agnostic):** `{ value, confidence, probabilities }`.
  Fase 2 fills it from weighted keywords (mode C: reuse of the turn's scores
  where available); Fase 3 fills it from the composer endpoint. `decide()`
  consumes only this shape, so the frontend is ready for any source without
  rewiring.

### Endpoint: POST /api/composer/intent (composer-v1, Fase 3)

- **Request:** `{ "text": "<1..2000 chars>" }`. No session, no persona: the
  endpoint classifies text only, so it stays cacheable with minimal PII
  surface.
- **Response:** `{ intent: { value, confidence, probabilities },
  question_set: "composer-v1", model, cached: bool }`, where composer-v1 =
  intent question (N options) + clear_enough binary, reusing calibrated
  (question_type, option_count) shapes.
- **Errors:** 422 on bad text; dedicated 429 pool with `Retry-After` (a typing
  user at ~3 calls/s must never eat the 120/min turn budget — dedicated
  limiter mandatory, not optional). No 403/503-passcode once the demo is open.
- **Semantics:** the preview is not authoritative; suggests are not decisions,
  so this endpoint writes nothing to `decisions.jsonl` (exception to be
  documented in DECISIONS.md when it lands, not by this spec).
- **Load discipline:** client debounce trailing >= 300 ms + abort + dedupe +
  minimum interval; server LRU cache on (normalized text, set version).

### Nivel A (Fase 2, no backend change) vs Nivel B (Fase 3, conditional)

- **Nivel A — choreographed reveal:** the client reveals dossier stages from
  real events only: `received → classifying → searching → verifying →
  awaiting_confirmation | completed | escalated | failed`. With a single
  non-streaming reply, intermediate stages are timed presentation over the
  pending turn, labelled honestly (copy says "waiting for the hub", never a
  fake tool name). A pending turn shows `busy`; completed stages map 1:1 to
  trace steps once the reply arrives.
- **Nivel B — SSE (conditional):** only if the F2.6 spike validates
  SSE-through-Vercel against the deployed topology. Design deferred to the
  spike outcome; the contract wave (F3.2/F3.3) does not assume streaming.
- **Q1/Q2 gates (TBD — pending probes F3.0a/b):** the composer endpoint ships
  only on GO. Q1: p95 of the composer set on the Space; GO if <= 800 ms,
  fallback to mode C if > 1500 ms, grey zone 800–1500 ms with 500 ms debounce
  + aggressive cache and re-measurement. Q2: PT confidences comparable to ES;
  else Laya morph ES-only with keyword fallback in PT. If Q1 fails, Fase 3 =
  F3.2 + F3.3 + F3.5 + F3.6 (no composer endpoint).

### presentation-policy-agnostic ( vocabulary.ts + v3 runbook )

- `frontend/app/vocabulary.ts`: registry id → `{ label, tone, icon }` per
  language, with raw-key fallback (unknown route / rule / verdict renders the
  key, never blanks, never crashes). Open unions in `types.ts`: new keys flow
  through without type edits.
- Score bars read their denominator from `summary.threshold` in the trace;
  thresholds are displayed, never stored, in the frontend.
- **v3 runbook (T-C + contingent T-E):** on `policy/v3.yaml` promotion, the
  frontend needs no code change: new rule/route ids render via fallback until
  labelled; bars re-anchor to the new `summary.threshold` automatically. T-E
  (contingent re-tuning) applies only if labels or copy reference a removed
  semantic.

## Behaviour

- Voice is transcription only: the mic button → browser permission → recording
  indicator → editable transcript → user confirms → sent as `text`. The
  backend processes transcription exactly like typed text. Original audio never
  leaves the browser; an audio-attachment contract is a separate future
  proposal, not claimed here. Denied permission and unsupported browsers
  degrade to the text input with an explanatory chrome string. Optional spoken
  replies via speech synthesis reuse only `reply` text.
- The composer preview (ghost / choose / committed) is advisory: sending the
  text always issues the normal `POST /api/hub/message`; the preview never
  alters the payload in Fase 2.
- Cards accumulate across turns into `CaseStudy.cards`; the turn view keeps
  showing the single `card` per reply (TSD-010 unchanged). `awaiting` states
  distinguish scaled-escalation from parked-approval; a queued case shows the
  case panel. Multi-card-per-turn rendering waits for the contract wave.
- Chain of Thought renders `trace.stage → step name`, `rule_id → applied
  rule`, `verdict → step status`, `summary → description`, `scores →
  visible metrics`. Port the real AI Elements `chain-of-thought.tsx` source to
  React 18 + plain CSS (Radix Collapsible supports React 18 [vendor]); the
  `Reasoning` component is rejected (no streaming; private-model reasoning
  must never render).
- Attachments stay local-only or are removed per D2: a file shown in the UI is
  labelled "not analysed" unless a future contract processes it. No proposal
  in this spec implies backend file analysis.
- Errors: backend down, mic denied, no voice support, 404 / 429 / 503 /
  invalid payload each map to a `CaseStatus.error` dossier state with a
  retryable chrome message; the failed turn keeps its message and error, as
  today.
- Contract-touching rule: any change to `HubReply` drags `types.ts` → UI →
  `scripts/check_deployment.py` + `tests/deployment/` → spec + CHANGELOG +
  DECISIONS in the same PR.

## Workflow context (decisions 10, 17; D1–D5 proposed)

The stuck-payments workflow (decision 17) is complete; this spec only surfaces
it progressively. Decision 10's rejected alternative — LLM-generated UI — stays
rejected through every phase.

D1–D5 are proposed by this spec, registered in DECISIONS.md only when their
code lands: D1 port the real Chain-of-Thought source (intermediate option) and
keep the rest as local adapters; D2 drop attachments or keep them labelled
local-only; D3 Nivel A first, Nivel B only on a validated spike; D4 rebase the
existing premium branch into compliant commits rather than starting over; D5
port `decide.ts` + registry with no online Jev, Laya as the later source via
the composer endpoint. The Laya-as-Jev validation concluded GO-conditional
with Q1/Q2 as mechanical gates (see Nivel A/B above).

## Tests and acceptance

- Fase 1 (foundation, separate PRs): pytest + git rules + `npm run lint` /
  `npm run build` green; 7 scenarios manual OK; smoke green; this spec merged.
- Fase 2 (zero backend change): voice-local test (voice → editable text, no
  backend call); current-contract message test (text → `HubReply` → visual
  card); case-study test (initial card → backend-updated → final card);
  traceability test (`trace` → ChainOfThoughtStep, backend data only); parked
  action test (`awaiting_ref` → confirm → resume → updated reply); error
  matrix (backend down, mic denied, no voice support, 404 / 429 / 503 /
  invalid payload). Done when the premium demo runs all 7 scenarios ES/PT
  with green checks and `service.py` plus the smoke untouched.
- Fase 3 (conditional): composer endpoint pytest offline (req/res/429/cache,
  no decisions logged); Q1/Q2 probes with pre-committed thresholds; SSE spike
  verdict before any Nivel B design. Done when the live premium demo runs with
  or without the endpoint per measurement, docs current.
- Docs-only verification for this spec PR: read the spec, `git status` clean
  of non-docs paths; pytest N/A (no code), noted in the PR.

## PR checklist for future code (from the PR template)

Every implementation PR under this spec fills `.github/pull_request_template.md`
with: Conventional title + branch `<type>/<short-description>`; small logical
commits per the agreed plan (any `Size-exception:` reasoned); tests added and
passing; CHANGELOG `Unreleased` entry (conserve parallel bullets at merge);
README/docs updated if behaviour or setup changed; new design decisions in
`docs/DECISIONS.md`; no data / credentials / weights / artifacts; only the
permitted Factory trailer on Markdown-only commits.
