# TSD-022: Intent-Driven Customer App and Visual Investigation

| | |
|---|---|
| Status | implemented |
| Branch | `feat/intent-driven-customer-app` |
| Depends on | TSD-003, TSD-010 |
| Required by | the deployment demo (T-304) |
| Requirements | PRD FR-7, FR-8, FR-12, FR-13; UC-1 to UC-5, UC-7, UC-8 |
| Design | DESIGN.md 2, 6; decisions 10, 17, 30, 38 |

## Purpose

Evolve the customer application from a static chat interface into a visual investigation experience. The client-side interaction is driven by Intent-Driven Cards that morph into structured widgets based on typed or voice input (Web Speech API). The ongoing conversation aggregates into a progressive `CaseStudy` dossier that presents verified tool evidence, auditable trace steps using AI Elements (`ChainOfThought`), and unambiguous human-in-the-loop controls, while keeping Calvino's backend contracts (`HubReply`) and policy-driven routing completely authoritative.

## Interfaces and data models

1. **CaseStudy conceptual model (`frontend/app/types/case-study.ts`):**
   - `id`: Backend `case_ref` when issued, or client turn identifier.
   - `title`: Dynamic case title derived from transaction reference or detected intent.
   - `status`: Lifecycle state (`draft`, `analyzing`, `needs_information`, `awaiting_action`, `in_operator_queue`, `resolved`, `refused`).
   - `intent`: Detected local intent (`split`, `checklist`, `status_track`, `action_retry`, `action_cancel`, `dispute`, `conversation`).
   - `input`: Raw input text, transcription flag, and local-only attachments.
   - `cards`: Verified cards from PRD FR-7 accumulated across case turns.
   - `evidence`: Authoritative route, human intervention flag, calibrated Laya scores, and audited facts.
   - `pendingAction`: Parked interrupt state (`approve_action` or `operator_queue`) and `awaiting_ref`.
   - `trace`: Ordered `TraceStep` records from `decisions.jsonl`.
   - `finalResponse`: Verified text reply from Calvino.

2. **Policy-Agnostic Vocabulary Registry (`frontend/app/vocabulary.ts`):**
   - Open union typing for stages, routes, verdicts, and rules (`KnownRoute | (string & {})`).
   - Mapping of technical IDs to human-readable i18n labels and visual tones (`ok`, `warn`, `danger`, `info`).
   - Comparison of calibrated scores against `summary.threshold` without hardcoded UI constants.

3. **Intent-Driven Morphing Engine (`frontend/app/components/intent-driven/`):**
   - Local deterministic classifier detecting banking intents and computing parameters (split totals, checklist items, transaction references).
   - Reactive interactive widgets: `SplitMorph`, `ChecklistMorph`, `StatusTrackMorph`.
   - Voice input integration via `useSpeechRecognition` with clean fallback on unsupported browsers.

4. **Auditable AI Elements (`frontend/app/components/ai-elements/`):**
   - `ChainOfThought`: Step container mapping directly to `trace: TraceStep[]`.
   - `ReasoningStep`: Displays stage, rule ID, description, calibrated score bars with threshold indicators, and facts summary. No simulated or private model reasoning is rendered.

## Behaviour

- The user types or speaks via microphone; the input dynamically reflects the detected intent.
- Submitting the input initiates a `CaseStudy` in `analyzing` state and posts `{ persona, text }` to `/api/hub/message`.
- Upon receiving `HubReply`, the case updates with the verified reply, official catalog card, and trace steps.
- If the action is parked for customer approval (`awaiting === "approve_action"`), the case displays `awaiting_action` and binds the confirm/deny buttons to `awaiting_ref`.
- If the action is queued for a human operator (`awaiting === "operator_queue"`), the case displays `OperatorQueuePanel` with an isolated per-turn resolution form.
- The GlassBox / CaseDossier renders only what the harness audited, preserving the verdict-driven UI principle.

## Tests and acceptance

- `npm run lint` passes with 0 warnings and 0 errors.
- `npm run build` completes successfully.
- Core pytest suite (`tests/calvino`, `tests/scenarios`, `tests/deployment`) passes 100% green (1042 passed).
- All 7 scenario buttons (UC-1 to UC-5, UC-7, UC-8) trigger their respective routes and cards without regression.
