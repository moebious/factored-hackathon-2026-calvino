# TSD-010: Customer app with Laya cards

| | |
|---|---|
| Status | proposed |
| Branch | `feat/customer-app` |
| Depends on | TSD-003, TSD-009 |
| Required by | the deployment (T-304), the evaluation demo (T-303) |
| Requirements | PRD FR-7, FR-8, FR-12, FR-13; UC-1 to UC-5, UC-7, UC-8 |
| Design | DESIGN.md 2, 6; decisions 10, 17 |

## Purpose

The demo link's main screen (decision 10): cards chosen from a fixed catalog and filled only from verified data, a glass-box panel showing scores, rules, tool results and verifier verdicts, scenario buttons for every use case, and an ES / PT toggle. The UI is a verdict: the hub emits a card key plus payload, and the app renders it with the fixed component for that key. Nothing on screen is free-form generation.

Three pieces, in one spec because each is small and none ships alone:

1. **Hub additions** so every FR-7 card exists and the glass box has data: `payment_status`, `action_result` and `case_status` cards emitted from verified tool results, the `action_confirmation` card mapped from the parked `approve_action` interrupt, and a per-turn decision trace on `HubReply`.
2. **Hub HTTP endpoints** in `calvino.api`, behind the existing passcode and rate limit.
3. **The Next.js customer app**, replacing the minimal TSD-003 demo frontend.

The language work stays deterministic until T-301 lands the LLM agent: a `TemplateAgent` drafts grounded templated replies from the playbook and the verified tool results. Decision 10 asks for exactly this: no free-form text on screen while the thesis is being judged.

## Interfaces and data models

**Card catalog (fixed; the union of what the hub can emit):**

| Key | Payload | Emitted by |
|---|---|---|
| `payment_status` | entry_reference, amount, currency, status, merchant?, date? | explain, from the `get_entry_detail` result |
| `problem_transactions` | entries (reference, amount, currency, status, date) | clarify (exists) |
| `action_confirmation` | action, entry_reference, amount, currency | the service, from the parked `approve_action` payload |
| `action_result` | action, entry_reference, status | act, from the verified read-back |
| `case_opened` | case_ref | handoff / escalate (exists) |
| `case_status` | case_ref, status | follow_up, from the `get_investigation_status` result |
| `human_path` | {} | out of scope (exists) |
| `refusal` | rule | any refusal (exists) |

**Hub changes (`calvino.hub`):**

- `TraceStep(stage, rule_id, verdict, summary)`: one decision record as the glass box shows it. `HubReply` gains `trace: tuple[TraceStep, ...]`; `HubService` collects the records the turn appended by diffing the decision log around the invoke.
- `DEMO_PERSONAS` (ana, camilo, lucia, dana → fixture customer ids) moves from the test conftest to `calvino.hub.sessions`; the conftest imports it, one source.
- `TemplateAgent` implements `Agent` with a fixed plan per stage: focus the entry (the reference in the message, else the single problem entry), fetch its detail, then draft a grounded sentence from the playbook guidance and the verified payload — never a field the payload lacks. Spanish replies in this task; Portuguese replies land with the T-301 agent.

**API (`calvino.api`):**

- `POST /api/hub/message` `{persona, text}` → `HubReply` JSON (reply, card, route, case_ref, escalated, awaiting, awaiting_ref, trace).
- `POST /api/hub/resume` `{ref, decision}` → `HubReply` JSON; `decision` is the customer's approval (true) or denial (false) for `approve_action`, the operator's decision string for `operator_queue`.
- `GET /api/hub/personas` → the demo persona names.
- Same passcode header and per-client rate limit as `/api/demo/decide`; disabled without a configured passcode (fail closed). The hub service is wired at startup: policy v1, `BankTools` on the dataset adapter over the bundled synthetic fixture, `TrustedSessionIssuer(DEMO_PERSONAS)`, `TemplateAgent`, the decision log and the confirmation issuer from `calvino.tools`, and a fraud context over the fixture's flags.

**Frontend (`frontend/`):** one screen: persona selector, conversation (customer messages and Calvino replies), the card under each reply, an input box, scenario buttons, the ES / PT toggle for the UI chrome, and the glass-box panel for the selected turn (trace steps with stage, rule, verdict and the classifier's scores; tool results; verifier verdicts). One component per catalog key, rendered only from the payload; an unknown key renders a named fallback card, never a crash. Scenario buttons set the persona and send the scripted message for UC-1 to UC-5, UC-7 and UC-8.

## Behaviour

- explain emits `payment_status` when a `get_entry_detail` result is focused and the reply passed verification; act emits `action_result` after the write's read-back; follow_up emits `case_status`. Cards are filled only from tool payloads (FR-7).
- A parked `approve_action` turn returns the `action_confirmation` card plus `awaiting_ref`; the confirm button resumes with `decision: true`, deny with `false` (a denial escalates to a person, as today).
- Every turn's trace carries its decision records in order; the glass box reads only the trace, so the panel can never show data the harness did not log.
- The API rejects an unknown persona or ref fail-closed (404/KeyError → HTTP 404), and texts over the demo bound (413/422 as the decide endpoint does).

## Workflow context (decisions 10, 17)

The stuck-payments workflow (decision 17) is complete in the hub; this task only surfaces it. Decision 10's rejected alternative — LLM-generated UI — stays rejected: the catalog is code, the choice is Laya's through the policy, and the scenario buttons exist so judges see every use case within seconds.

## Tests and acceptance

- Hub: trace collection across `handle_message` and `resume` (service tests); `payment_status`, `action_result` and `case_status` emitted from scripted tool results (graph tests); `TemplateAgent` drafts only from the payload and the playbook (unit tests, no model calls).
- API: pytest with the existing fakes — passcode required, rate limit applies, message happy path returns card and trace, resume completes a parked approval, personas endpoint, unknown persona and ref fail closed.
- Frontend: `npm run lint` and `npm run build` pass; a catalog component exists for every key.
- Done when: UC-1 to UC-5, UC-7 and UC-8 can each be shown from a scenario button against the local API (`uv run python -m calvino.api` + `npm run dev`), the glass box shows the turn's scores, rules and verdicts, and the full pytest suite and frontend checks pass.
