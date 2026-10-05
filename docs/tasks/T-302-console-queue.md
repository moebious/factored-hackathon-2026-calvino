# T-302: Handoff queue and audit timeline

| | |
|---|---|
| Wave | 3 |
| Status | done |
| Branch | `feat/console-queue` |
| Spec | [TSD-023](../specs/TSD-023-operator-console.md) |
| Depends on | T-204 |
| Blocked by | — |
| Model | standard model |
| Can run in parallel | yes |
| References | decision 11; PRD FR-9, FR-10, FR-11; PRD UC-6, AC-4 |

**Goal.** The usable System 3 workspace: cases requiring accountable human judgment, with verified evidence and every refusal named (decision 37).

**Inputs.** the case file and decision log

**Outputs.** a queue view (actions awaiting approval and open investigations), a case view (verified facts, actions, evidence, open questions), approve/deny, edit customer-facing replies and case notes, and take over through governed paths; an audit timeline naming the rule on every refusal. Preserve original and edited text, actor and reason. Source bank evidence is immutable in the workspace; disputed evidence prompts a new verified read, not an overwrite. Edited replies are rechecked for factual disclosure before sending. Human approval cannot override a Gate `block`.

**Open parameters.** none

**Done when.** PRD UC-6 and AC-4 work through an operator's real queue and case workspace, attributable edits and takeover appear in the audit trace, and tests prove neither an edited reply nor a human approval bypasses ownership, eligibility or the Gate's block.

**Completed:** TSD-023 approved in #89. Backend `GET /api/hub/cases` with fallback demo seeds, Gate block enforcement on `/api/hub/resume`, Next.js `/console` route with `OperatorQueueTable`, `OperatorCaseDossier`, `ActionApprovalBar`, `AttributableReplyEditor`, and bilingual ES/PT parity implemented on `feat/console-queue`.

