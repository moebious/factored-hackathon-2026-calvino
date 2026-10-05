# TSD-023: Operator Workspace and Audit Timeline

| | |
|---|---|
| Status | proposed |
| Branch | `feat/console-queue` |
| Depends on | TSD-009, TSD-010, TSD-022 |
| Required by | T-302 (Operator workspace), T-401 (Durable cases), T-304 (Deployment demo) |
| Requirements | PRD FR-9, FR-10, FR-11; PRD UC-6, AC-4 |
| Design | DESIGN.md 2, 4.0, 6.1; decisions 11, 21, 35, 37 |

## Purpose

Provide the human-in-the-loop workspace (System 3) for bank customer service operators and supervisors.

While the customer application (TSD-010, TSD-022) visualizes customer turns and parks uncertain cases, the Operator Workspace provides an operational interface to manage all parked cases, review verified evidence dossiers, approve or deny gated actions, and author attributable replies without compromising banking safety rules.

Core governance rule (decision 37): **A human operator cannot override a Gate `block`.** Human authority is restricted to adjudicating gray-zone actions (`GateVerdict.ASK`), providing accountable explanations, and conducting investigations with immutable bank evidence.

## Interfaces and Data Models

### 1. Hub & API Additions (`calvino.api` & `calvino.hub`)

* **Endpoint `GET /api/hub/cases`**:
  Lists all cases currently in the operator queue or pending human approval.
  
  ```python
  class OperatorQueueItem(BaseModel):
      case_ref: str
      persona: str
      status: Literal["pending_approval", "in_investigation", "refused", "resolved"]
      reason_rule_id: str
      created_at: str
      customer_message: str
      entry_reference: str | None = None
      amount: str | None = None
      currency: str | None = None
      target_action: Literal["cancel_payment", "retry_payment", "open_investigation"] | None = None
      awaiting_ref: str | None = None
      gate_verdict: str | None = None
  ```

  *Cold-start fallback*: If the runtime checkpointer or decision log has no active parked cases (e.g. during fresh container starts), the endpoint returns pre-seeded representative cases for UC-4 (`ana`: explicit human escalation) and UC-6 (`lucia`: high-value transfer awaiting gray-zone approval), ensuring judges can immediately evaluate System 3.

* **Endpoint `POST /api/hub/resume`**:
  Reuses the existing `HubResumeRequest` schema:
  * For `approve_action` interrupts: `decision=True` (approve) or `decision=False` (deny).
  * For `operator_queue` interrupts: `decision="Operator response and resolution text"`.

* **Attributable Audit Logging (`calvino.records`)**:
  Appends an operator resolution record to `decisions.jsonl` containing:
  `actor_id` (`operator:demo-agent-01`), `case_ref`, `original_action`, `operator_verdict`, `justification`, and `timestamp`.

### 2. Frontend Architecture (`frontend/app/console/`)

* **Route**: `frontend/app/console/page.tsx`
* **Components**:
  1. `OperatorQueueTable`: Displays pending cases with filtering by urgency, status, and persona.
  2. `OperatorCaseDossier`: Detailed panel rendering customer facts, focused transaction details, Laya calibrated scores, and the immutable audit timeline.
  3. `ActionApprovalBar`:
     * When `gate_verdict === "ask"`: Displays single-use token parameters with explicit **Approve** and **Deny** buttons.
     * When `gate_verdict === "block"`: Approval buttons are disabled. Displays a persistent banner naming the refusal rule (`TOOL-NOT-OWNER`, `GATE-AMOUNT-LIMIT`, `TOOL-FRAUD-FLAGGED`).
  4. `AttributableReplyEditor`: Side-by-side view comparing Calvino's suggested draft against operator edits before sending.
  5. `AuditTimeline`: Chronological step-by-step history from customer message through Laya classification, policy routing, and human resolution.
* **Top Navigation Bar Switcher**:
  Both `/` (Customer App) and `/console` (Operator Workspace) feature a unified top switcher allowing judges to toggle perspectives in one click.

## Behaviour and Safety Invariants

1. **Gate Block Immutability**: If a transaction is blocked by deterministic hard rules or Gate policy, the operator console strictly prevents executing the tool write. The only available paths are customer notification and opening a formal bank investigation.
2. **Attributability**: Every operator override, note, or approval records the operator's identifier in the permanent audit trail.
3. **Evidence Immutability**: Bank transaction amounts, dates, and statuses shown in the console are read-only. Disputed facts trigger a fresh read tool call, never an in-place edit of bank data.
4. **Bilingual Parity**: All console labels, status indicators, and operational buttons support full Spanish and Portuguese parity via `i18n.ts`.

## Tests and Acceptance

1. **Backend Integration**:
   * Test `GET /api/hub/cases` returns active parked turns from `HubService`.
   * Test `GET /api/hub/cases` serves fallback seeded cases when the checkpointer is empty.
   * Test resuming a parked action via `POST /api/hub/resume` executes the gated action only when `decision is True`.
   * Test that an operator cannot approve an action marked with a Gate `block`.
2. **Frontend Quality**:
   * `npm run lint` passes with 0 errors and 0 warnings.
   * `npm run build` completes cleanly with static generation of `/console`.
   * Interactive test: Selecting a case in `OperatorQueueTable` updates `OperatorCaseDossier` and allows completing approval or denial with instant UI update.
