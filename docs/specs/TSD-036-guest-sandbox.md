# TSD-036: Guest Sandbox Sessions for Persona-Agnostic Customer App

| | |
|---|---|
| Status | proposed |
| Branch | `feat/guest-sandbox` |
| Task | [T-409](../tasks/T-409-guest-sandbox.md) |
| Depends on | TSD-010 (Customer app), TSD-009 (Hub service), TSD-028 (Conversational experience) |
| Required by | Live evaluation demo, public judging link (T-306, T-307) |
| Requirements | PRD FR-7, FR-12, FR-13; UC-1 to UC-8 |
| Design | DESIGN.md 2, 6; decisions 10, 17, 38 |

## Purpose

Decouple the public customer frontend from hardcoded demo personas (e.g. `ana`). Enable any visitor to interact with Calvino as an open guest without manually selecting an identity, sharing conversation threads with other visitors, or assuming real-bank customer credentials.

The demo operates as an **unauthenticated guest sandbox**:
1. Ordinary visitors send chat messages without specifying a persona or identity in the UI payload.
2. The server provisions an opaque, short-lived guest session bound to a controlled synthetic sandbox customer (`C-MX-001`), isolating conversation threads per guest.
3. Pre-scripted guided scenarios remain available as explicit demo exploration paths, cleanly segregated from guest conversations.
4. Mobile and desktop UI header cleans up persona selectors, replacing them with a clear "Sandbox Demo" badge.

## Core Architectural Invariants

1. **Server-Managed Session Integrity**: The frontend never holds bank credentials, customer IDs, or raw session tokens. The client only carries an opaque `guest_id` (cookie or header/payload) or server-managed thread reference.
2. **Guest Thread Isolation**: Each guest receives a unique LangGraph thread (`guest-{guest_id}`). Multiple concurrent visitors do not collide on thread history, interrupts, or turn traces.
3. **Fail-Closed Scoping**: Action approvals, resumes (`POST /api/hub/resume`), and case references cannot be resumed across different guest threads.
4. **Deterministic Sandbox Grounding**: In guest chat, tools bind only to verified records in the synthetic bank fixture under the guest's assigned sandbox customer.
5. **Scenario Preservation**: Seeded exploration chips (UC-1 to UC-8) remain fully functional for evaluators and judges as guided reference scenarios.

## Interfaces and Data Models

### 1. Hub & Session Issuer (`calvino.hub.sessions`, `calvino.hub.service`)

**Session Issuer:**
```python
SANDBOX_DEFAULT_CUSTOMER_ID = "C-MX-001"  # Ana's rich dataset profile in synthetic_bank.json


class TrustedSessionIssuer:
    ...

    def issue_guest(
        self, guest_id: str, customer_id: str = SANDBOX_DEFAULT_CUSTOMER_ID
    ) -> tuple[str, str]:
        """Issue an opaque session token and hashed ref for a sandbox guest."""
```

**Hub Service:**
```python
class HubService:
    ...

    def handle_message(
        self,
        text: str,
        persona: str | None = None,
        guest_id: str | None = None,
    ) -> HubReply:
        """Handle a customer turn.

        If persona is provided, runs on thread f"persona-{persona}" (legacy/guided scenario).
        If guest_id is provided (or generated), runs on isolated thread f"guest-{guest_id}".
        """
```

### 2. API Contract Changes (`calvino.api.app`)

**Updated `HubMessageRequest`:**
```python
class HubMessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_DEMO_TEXT_CHARS)
    guest_id: str | None = Field(default=None, max_length=64)
    persona: str | None = Field(default=None, max_length=32)
```
- If `persona` is omitted, backend uses or generates `guest_id`.
- Returns `guest_id` in response headers or attached to `HubReply` so the browser maintains session continuity across turns.

**Resume `HubResumeRequest`:**
- Validates that the resuming `ref` corresponds to the caller's active session or guest thread.

### 3. Frontend Contract & UI Changes (`frontend/`)

1. **`useHubConversation` hook:**
   - Generates or stores a persistent local `guest_id` (`crypto.randomUUID()` in `sessionStorage`).
   - Normal `send(message)` sends `{ text: message, guest_id }`.
   - `sendScenario(scenario)` sends `{ text: scenario.message, persona: scenario.persona }`.
   - Clears hardcoded default persona "ana" from state.
2. **`page.tsx`:**
   - Remove `<label className="persona-select">` dropdown.
   - Replace with a sleek "Sandbox" indicator pill (`ShieldCheck` / `Sparkles`).
   - Refresh button ("Nueva sesión" / "New session") to reset the guest conversation thread.
3. **Scenarios bar:**
   - Group scenario chips with a clear label: "Escenarios guiados (Evaluación)" / "Guided scenarios (Evaluation)".

## Test & Acceptance Criteria

1. **API tests (`tests/calvino/api/test_hub.py`)**:
   - `POST /api/hub/message` without `persona` succeeds, assigns a guest session, and returns a valid `HubReply`.
   - Two distinct `guest_id` values yield distinct LangGraph threads and separate histories.
   - Resuming a parked turn from an invalid/mismatched session fails closed with HTTP 403/404.
2. **Frontend unit / component checks**:
   - Type-checking passes (`npm run build` / `tsc`).
   - Default home view loads without persona dropdown; regular chat sends message without persona.
   - Scenario buttons still trigger their targeted persona evaluations.
3. **E2E verification**:
   - Run end-to-end multi-turn conversation in guest mode. Verify glass box trace, card emission, and confirm/deny actions work seamlessly.
