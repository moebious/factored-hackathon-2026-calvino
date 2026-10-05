# TSD-016: Support agent (LLM language work in the hub)

| | |
|---|---|
| Status | implemented, with the amendments below |
| Branch | `feat/llm-agent` |
| Task | T-301 |
| Depends on | TSD-009 (hub), TSD-011 (LLM client), TSD-004 (verifier) |
| Required by | T-303 (the end-to-end evaluation measures the LLM agent, not the template) |
| Requirements | FR-6, FR-7, NFR-1, NFR-7 |
| Design | DESIGN.md 4.0, 6.1; decisions 10, 15, 20, 24, 28, 29 |

## Purpose

Put the Qwen model behind the hub's existing `SupportAgent` seam, so replies are written by a
language model and checked by the verifier cascade, instead of filled into templates.

The model writes **language only**. The harness keeps the plan: which tools run, which payment is
in focus, and whether a customer asked to cancel or retry (a literal keyword scan, decision 10).
The model never names a tool, a customer or an action, so a write cannot be prompted into
existence; the Gate (TSD-009) still rules on every write exactly as it does today.

This narrows the T-301 card, which describes a Deep Agents worker that picks its own tool calls.
That variant stays a later option (`LlmAgent` and a tool-calling agent are both `SupportAgent`s);
this spec is the smaller change that makes the evaluation measure model-written replies.

## Interfaces

**`LlmAgent`** (in `calvino.hub.llm_agent`) implements `SupportAgent`:

- `LlmAgent(client: ChatClient, planner: SupportAgent = TemplateAgent(), prompts: PromptSet)`.
- `draft(request) -> AgentDraft`:
  1. Ask the planner for the step. If it returns tool calls, return them unchanged: the model
     is not involved in planning.
  2. If it returns text, that text is the **fallback and the fact skeleton**. Build a prompt from
     the request and call `client.complete`, with `Role.AGENT`, a fixed `seed` and a completion
     budget sized for a reasoning model (TSD-011: a tight budget is spent thinking).
  3. Return the model's text, validated (below), as `AgentDraft(text=...)`.
- On `request.feedback` (the verifier's single retry), the failed criteria go into the prompt
  as corrections; the retry is a fresh call, not a chat continuation.
- Fixed replies the planner produces without a payload to cite (`NO_PROBLEMS_REPLY`,
  `PICK_REPLY`, `NO_CASE_REPLY`) are not sent to the model: there is nothing to write about.

**Prompt inputs** are verified facts only: the stage, the playbook guidance for the status
(decision 24), the tool-result payloads the reply may cite (`request.tool_results`), the
customer's message as redacted by `redact_question` (the digest TSD-004 already builds), and the
feedback. The session token is not a field of `AgentRequest` and so cannot reach the prompt
(AGENTS.md design rule).

**Prompts** live in `prompts/support-agent-v1.yaml`, one system prompt per stage (explain, act,
follow-up), versioned like the policy and playbook: a released file is never edited. The version
is recorded in the run header and in each decision record's `versions`.

**Wiring.** `build_hub_service` and the evaluation runner accept an optional `SupportAgent`.
Both build an `LlmAgent` when `CALVINO_LLM_API_KEY` and `CALVINO_LLM_MODEL` are set and the
`TemplateAgent` otherwise, so the demo and tier0 keep working with no keys. The run header and
the report name which agent answered; `run_evaluation.py` no longer prints the agent model for a
run that used the template.

## Behaviour

**Guards on the model's text** (code, before the verifier; a failure is an `AgentDraft` error
the hub already escalates fail-closed as `AGENT-ERROR`):

- non-empty, within a length cap, a single reply (no tool-call syntax or markdown fences);
- `finish_reason` is not `length` (`LlmTruncated` is raised by the client and handled the same
  way);
- on any `LlmError`, the agent raises and the hub escalates. It does **not** silently fall back to
  the template: a reply the evaluation attributes to the model must have been written by it.

**Language.** The reply is in the language of the customer's message (ES default, PT when the
message is Portuguese). The code checks accept Spanish and Portuguese status words (TSD-004).

**What the verifier still decides.** Amounts, dates, statuses and action claims are checked
against the tool payloads by the existing code checks and the judge; the prompt tells the model to
cite those fields verbatim and to claim an action only when a read-back result is present, but the
prompt is not the control.

**Cost and latency.** Each model call records its tokens and latency; the evaluation sums
`prompt_tokens`/`completion_tokens` into cost using prices from `providers.yaml`
(a new `price_per_million_tokens` field per role, `null` while unrecorded, so cost is reported
as `not priced` rather than $0). The client's limiter keeps the run below Hetzner's cap.

## Out of scope

- Model-chosen tool calls or actions (a tool-calling agent, the Deep Agents worker).
- Retrieval over policy documents ("company brain"): the playbook is the knowledge source.
- Changing the policy, Gate, verifier rubric or playbook.
- Portuguese scenarios and cases (T-203).

## Tests and acceptance

Offline, with `FakeChatClient`; no network, GPU or real dataset:

1. Planner tool calls pass through untouched and make no model call.
2. A payload step calls the client once, with a prompt containing the payload fields, the
   playbook guidance and the redacted message, and never the session token or another
   customer's markers (assert on the recorded request).
3. Feedback from a failed criterion appears in the retry prompt.
4. Guards: empty, over-length, truncated and tool-syntax replies raise; an `LlmError` propagates
   and the hub turn escalates as `AGENT-ERROR` (graph test).
5. A hub scenario (UC-1) with a scripted `FakeChatClient` reply passes the verifier; a reply that
   states a wrong amount fails the code check, is retried once, and escalates if it fails again.
6. The runner reports the agent that answered, the model, the prompt version, and tokens and
   latency per case; tier0 without keys still runs and says "TemplateAgent".
7. Prompt file: loads, validates, and rejects an edit of a released version (by hash).

Done when the `--suite all` evaluation scores the 50 cases with `LlmAgent`, the report header
names the model and the prompt version, and its headline comparison against the template run is
committed. Acceptance on the scripted scenarios in Spanish is part of this spec; Portuguese
waits on T-203.

## Amendments made while implementing

- **The real judge is wired in the evaluation.** The hub's default judge and Laya-tier checker are
  fakes that pass every criterion they own, so a model-written reply would have been checked by the
  code checks alone. `build_demo_hub` takes an optional `judge`, the evaluation builds the
  `OpenAiJudge` when the judge keys are set, and the report header names the hub judge that
  answered. No Laya checker is implemented yet.
- **The public demo stays keyless.** `build_demo_hub` takes an optional agent, but the demo API does
  not switch to the LLM when keys are present: a 25-30 s reply on a public link is a deployment
  decision, not a side effect of an environment variable.
- **Completion budget 8,192, not 2,048** `[measured]`: one real reply used 3,064 completion tokens
  and 2,048 ended truncated with no reply.
- **The header names the components that answered**, not the keys present: a run scored on the
  template, or with the MockJudge in the hub, says so. Unpriced tokens are reported as tokens.
- **The evaluation does not yet measure the model** `[measured]`: with live Laya only 2 of the 50
  cases reach the agent, and those end at the Gate with a refusal card, so the LLM wrote no reply
  in the suite. The tuning pass (HANDOFF next action 5) gates the acceptance run.
- **The NVIDIA judge times out in the hub** `[measured]` (all three judged criteria, 182 s),
  which fails closed. See decision 39.
- **T-301 is not finished by this spec.** The card as revised by decision 37 also asks for policy
  retrieval with cited evidence and Spanish and Portuguese replies under the verifier; both stay
  open here (the prompt file already carries a Portuguese language name, and no PT cases exist yet).

## Commit plan

1. `docs(agents)`: this spec and its index line.
2. `feat(agents)`: prompt file, loader and its tests.
3. `feat(agents)`: `LlmAgent` with the guards and its offline tests.
4. `feat(agents)`: wire the demo service and the evaluation runner, header and cost fields.
5. `docs(agents)`: decision entry, CHANGELOG, HANDOFF state.
