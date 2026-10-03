# TSD-009: Calvino hub

| | |
|---|---|
| Status | proposed |
| Branch | `feat/hub` |
| Depends on | TSD-000, TSD-001, TSD-002, TSD-004, TSD-005 |
| Required by | the support agent (T-301), the customer app (T-205), the operator queue (T-302), the evaluation (T-303), durable cases (T-401) |
| Requirements | PRD FR-1 to FR-11; AC-1 to AC-4, AC-6, AC-8 |
| Design | DESIGN.md 2, 4, 6.1; decisions 17, 20, 23, 24 |

## Purpose

System 1.5: wire the merged parts (policy engine, MCP tools, verifier, Laya) into the five stages of the stuck-payments workflow — explain, clarify, act under the Gate, investigate, follow up — as one LangGraph graph with a checkpointer and `interrupt()` for the human steps. Built without a real LLM provider: the support agent stays behind its interface with `ScriptedAgent` in tests, and the Qwen model of decision 20 is plugged in later (T-301) behind the same interface.

## Interfaces and data models

**Dependencies:** `langgraph` and `langgraph-checkpoint-sqlite` (the checkpointer's durable-case story is T-401; the hub wires the seam).

**Playbook (decision 24):** `playbooks/stuck-payments.yaml`, versioned like the policy — a released version is never edited. Per status (Pending, Declined, Reversed): what to explain, which actions to offer, when to escalate. `calvino.hub.playbook`: `Playbook`, `StatusGuidance`, `load_playbook` (same loader pattern as `policy/config.py`). The agent's prompt context and, later, the verifier's "valid next step" criterion both read it, so they cannot drift apart.

**Agent interface (decision 20):** `calvino.hub.agent`:

- `SupportAgent` protocol: `draft(request: AgentRequest) -> AgentDraft`.
- `AgentRequest`: stage, the customer's message, the verified facts (tool results) gathered so far, the playbook guidance for the status, and — on the verifier's retry — the failed criteria as feedback. **Never the session token** (design rule: the token never passes through a model).
- `AgentDraft`: `text` (the reply, or None when the agent asks for a tool first) and `tool_calls` (tool name plus arguments; the harness attaches the session).
- `ScriptedAgent` for tests: a queue of scripted drafts, records every request so tests can assert what the model would have seen.

**Trusted test sessions:** `calvino.hub.sessions`: `TrustedSessionIssuer` maps a persona (from the bank fixture, never a customer number typed in chat) to a session token; the hub issues it, attaches it to `BankTools` calls, and logs only `session_ref_for(token)`.

**Graph state:** `calvino.hub.state`: `HubState` (TypedDict): session ref, message, stage, facts, Laya answers and scores, route and gate decisions, gathered tool results, pending action and confirmation, case file, current draft, verification outcome, final reply.

**Graph:** `calvino.hub.graph`: `build_hub_graph(deps: HubDependencies) -> CompiledStateGraph`. Nodes: `intake` (session, Facts) → `classify` (Laya via the `SystemOneLoader` protocol reused from `calvino.api.loader`; `scores_from_answers` → `decide_route`, logged) → branch on the route:

| Route | Stage nodes |
|---|---|
| `agents` | `explain` loop: agent draft → run the stage's read tools (`BankTools`) → re-draft until the agent replies → `verify` |
| `clarify` | one question, or the problem-payment picker card from `list_problem_transactions`; the Gate refuses to act on a guess |
| `human` | `investigate`: case file (request, verified facts, actions, evidence, open questions), `open_investigation`, `interrupt()` for the operator queue |
| `out_of_scope` | an honest reply and a path to a person; no agent loop, no tools |

The `act` stage (reached from explain when the intent is cancel or retry): `decide_gate` → **allow** (run the write with its confirmation token and verified read-back), **ask** (`approve_action` `interrupt()`), **block** (refusal naming the rule, logged). `follow_up`: resume from the checkpoint, `get_investigation_status`, verified reply.

**Tools per stage (decision 24):** the graph exposes to the agent only the stage's tools — reads in explain, clarify and follow-up; plus `request_cancellation` and `retry_payment` in act; plus `open_investigation` in investigate. The Gate still checks every write (defense in depth).

**Service:** `calvino.hub.service`: `HubService.handle_message(persona, text) -> HubReply` and `HubService.resume(case_ref, operator_decision)`; the checkpointer lives on `CALVINO_DATA_DIR` (falling back to memory in tests). `HubReply`: reply text, card (from the fixed catalog, PRD FR-7 — the hub emits the card key and payload, the app renders it), route, case ref when escalated.

## Behaviour

- Hard rules run before Laya and always win: `Facts` come from the session, never from a model; `decide_route` fails closed to a human on missing scores.
- Every reply the customer sees passes the verifier cascade (TSD-004): `Verifier.run` with `regenerate` = one agent re-draft carrying the failed criteria; escalation writes the failed criteria into the case file and routes to a person (FR-6, AC-7).
- Every decision is logged as a `DecisionRecord`: the route (with scores, rule and policy version), each gate verdict, each verification attempt, and every tool refusal with its rule id (AC-6). Logs carry `session_ref`, never the token.
- Tool errors and refusals never reach the agent as raw text: the harness turns them into a named-rule refusal card or a clarify step.
- The same inputs and policy version give the same verdict (AC-8): the graph is deterministic apart from the agent and judge, which tests script.

## Workflow context (decisions 17, 20, 23, 24)

- Laya's question set is `workflow_questions()` from TSD-005 (workflow area, intent, clear enough, needs a person, injection), scored through `scores_from_answers`.
- The agent is a Qwen model through HF Inference Providers and the judge a DeepSeek model (decision 20); until the account exists, tests use `ScriptedAgent` and `MockJudge`, and the demo can run the whole graph with fakes.
- The acceptance scenarios (decision 23) are the first slice of the evaluation's test set: a scenario that passes never fails again.

## Tests and acceptance

End-to-end tests with fakes (`ScriptedAgent`, fake `SystemOneLoader`, `DatasetAdapter` on the bank fixture, `MockJudge`/`FakeLayaChecker`, sqlite or memory checkpointer — no network, GPU or dataset):

- Normal path: status explained from verified tool results, reply passes the cascade (AC-1).
- Ambiguous message: clarify question or picker; the Gate refuses to act on a guess (AC-2).
- Out-of-scope request: honest reply and a path to a person, no agent loop (AC-3).
- Hard-rule trigger (asks for a person): case file complete, operator queue, no agent step (AC-4).
- Other customer's data or injection: refused at the tool, the rule is named, the attempt is logged (AC-6).
- Replay: the same inputs and policy version give the identical verdict from the log (AC-8).
- Act stage: allow with confirmation and read-back; ask with `interrupt()` and resume; block with the rule named.
- Verifier failure: retry once with the failed criteria as feedback, then escalate with the case file (AC-7, from TSD-004).

`tests/scenarios/`: seeded scenario files (fixture record, message, expected route, expected tool calls, expected log records, expected card) for AC-1 to AC-4, AC-6 and AC-8, run on every pytest run with a scoreboard summary (decision 23).

**Done when** the end-to-end tests and the six scenarios pass in CI, every decision is logged, and the README run instructions still work.
