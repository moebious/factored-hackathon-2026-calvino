# TSD-025: Durable Cases and Process Restart Recovery

| | |
|---|---|
| Status | proposed |
| Branch | `feat/durable-cases` |
| Depends on | TSD-009, TSD-023 |
| Required by | T-401 (Durable cases), T-304 (Deploy demo) |
| Requirements | PRD FR-9, FR-10; PRD UC-6; AC-4 |
| Design | DESIGN.md 6.0, 6.1; decisions 17, 37 |

## Purpose

Ensure parked graph turns and operator cases persist across process restarts, container recycling (e.g. Hugging Face Spaces sleep/wake), and service reboots.

While T-302 (TSD-023) established the Operator Console and the `GET /api/hub/cases` / `POST /api/hub/resume` protocol, cases and thread-ref mappings are currently registered in process memory. If the backend process restarts:
1. Parked cases in the operator queue vanish from `/console`.
2. Although LangGraph thread checkpoints persist in SQLite (when `CALVINO_DATA_DIR` is set), the mapping from `case_ref` or `awaiting_ref` to `thread_id` is lost.
3. Resuming a parked turn fails because the original session token was discarded with the deceased process.

TSD-025 provides durable SQLite backing for cases and thread mappings, renewal of trusted session authority upon resume, and strict idempotency against duplicate execution.

## Invariants & Constraints

1. **Security & Token Hygiene (Non-Negotiable)**:
   Raw session tokens must **never** be persisted to disk, written to SQLite, or serialized into model-visible state. When resuming across restart, the service regenerates a fresh, verified session token for the case's verified persona using `deps.issuer.issue(case.persona)`.
2. **Double-Action Prevention (Idempotency)**:
   A case cannot be approved or denied more than once. The case status transition to `resolved` or `refused` is atomic. A second resume attempt on an already resolved case fails closed with a clear conflict error (`ValueError`), preventing duplicate payment retries or cancellations.
3. **Graceful Fallback & Cold-Start Compatibility**:
   When `CALVINO_DATA_DIR` is unset (e.g. standard unit test fixtures), the service uses an in-memory case store. When the store has zero cases, `GET /api/hub/cases` continues to provide seeded fallback cases for instant demo evaluation.
4. **Gate Block Immutability Preservation**:
   The safety invariant from decision 37 is strictly preserved across restarts: a case with `gate_verdict == "block"` cannot be approved by an operator after restart.
5. **No Regressions**:
   Existing Hub and API contracts (`HubReply`, `OperatorQueueItem`, `/api/hub/cases`, `/api/hub/resume`) remain fully backward-compatible.

## Architecture & Interfaces

### 1. Case Store Abstraction (`calvino.hub.storage`)

A dedicated persistence layer decoupled from graph internals:

```python
class CaseRecord(BaseModel):
    case_ref: str
    thread_id: str
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


class CaseStore(Protocol):
    def put(self, case: CaseRecord) -> None: ...
    def get_by_ref(self, ref: str) -> CaseRecord | None: ...
    def list_all(self) -> list[CaseRecord]: ...
    def update_status(self, case_ref: str, status: str) -> None: ...
```

* `SqliteCaseStore`: Persists records to `cases` table in SQLite (`hub-cases.sqlite` or `hub-checkpoints.sqlite` under `CALVINO_DATA_DIR`) with WAL mode and serialized transactions.
* `MemoryCaseStore`: Pure in-memory fallback for transient tests.

### 2. Session Authority Renewal on Resume

When `HubService.resume(ref, decision, actor_id, justification)` is called:
1. Lookup `CaseRecord` by `case_ref` or `awaiting_ref` in `CaseStore`.
2. Check idempotency: if `status` is already `resolved` or `refused`, raise `ValueError(f"case {case.case_ref} is already {case.status}")`.
3. Check safety rule: if `gate_verdict == "block"` and `decision is True`, raise `ValueError`.
4. Issue fresh session token: `token, _ = self._deps.issuer.issue(case.persona)`.
5. Invoke graph resume on `case.thread_id` with fresh `token`:
   ```python
   self._graph.invoke(
       Command(resume=decision),
       config={"configurable": {"thread_id": case.thread_id, "session_token": token}},
   )
   ```
6. Atomically update case status in `CaseStore`.
7. Log human decision to audit trail (`decisions.jsonl`).

### 3. Frontend Deep-Linking (`frontend/app/console/page.tsx`)

Support URL parameter `?case_ref=CASE-...`:
* When visiting `/console?case_ref=CASE-ANA-001`, the queue table automatically highlights the case and opens its `OperatorCaseDossier` and `ActionApprovalBar`.

## Verification Criteria

1. **Service Restart Simulation (`test_durable_cases_restart.py`)**:
   * Create `HubService` instance 1 with SQLite persistence.
   * Send message requiring escalation or action approval; verify turn parks with `awaiting_ref`.
   * Destroy instance 1.
   * Create `HubService` instance 2 with the same SQLite persistence.
   * Verify `list_cases()` in instance 2 contains the parked case.
   * Resume the case in instance 2 with operator decision.
   * Verify the turn completes successfully and the decision is recorded in audit logs.
2. **Duplicate Resume Protection**:
   * Attempting to resume the same case again in instance 2 raises `ValueError`.
3. **Gate Block Re-enforcement**:
   * Verify that a blocked case persisted before restart still rejects operator approval after restart.
4. **Token Security**:
   * Inspect SQLite table contents; verify zero session tokens or raw credentials exist in database columns.
