# T-409: Guest Sandbox Sessions for Persona-Agnostic Customer App

| | |
|---|---|
| Status | done |
| Branch | `feat/guest-sandbox` |
| Spec | [TSD-036](../specs/TSD-036-guest-sandbox.md) |
| Depends on | T-205, T-207, T-304 |
| Owner | maintainer |
| Type | standard |

## Why

The current public demo tightly couples every visitor to a fixed persona (`ana`), exposing a persona selector on desktop and silently forcing Ana on mobile. This causes all visitors to share Ana's thread history, prevents a realistic public customer banking sandbox experience, and confuses evaluators.

## Summary

1. Decouple `POST /api/hub/message` so it no longer requires `persona`. Provide server-managed guest sessions bound to a controlled synthetic sandbox customer profile (`C-MX-001`).
2. Isolate threads per guest (`guest-{guest_id}`) so concurrent users do not collide.
3. Update `frontend/` (`useHubConversation`, `page.tsx`) to remove persona selectors and replace them with a sandbox badge and a "Nueva conversación" reset control.
4. Preserve guided scenario chips (UC-1 to UC-8) explicitly as evaluator shortcuts.

## Acceptance Criteria

1. `POST /api/hub/message` accepts `{ text, guest_id? }` without `persona` and executes correctly.
2. Concurrent guests have isolated conversation threads.
3. Action approval resume cannot cross guest session boundaries (fail closed).
4. Persona dropdown removed from desktop and mobile headers in `page.tsx`.
5. Pre-scripted guided scenarios remain fully functional.
6. All backend pytest and frontend typescript builds pass cleanly.
