# Project Calvino: Product Requirements Document (PRD)

*What Calvino does and how we know it works. Why it exists is in [BRD.md](BRD.md); how it is designed is in [DESIGN.md](DESIGN.md); how each part is built is in [specs/](specs/).*

The workflow is stuck payments, end to end (decision 17; [DESIGN.md 6.1](DESIGN.md#61-the-workflow-stuck-payments-end-to-end)). Its intents are Laya's questions in DESIGN.md 6.1, its tools are in TSD-002, and its cards are in FR-7.

## 1. Users

| User | Uses | Needs |
|---|---|---|
| **Customer** | customer app | an answer or action they can trust, in their language, without a wall of text |
| **Human agent** | operator console | cases that truly need them, with verified facts, actions taken, evidence and open questions |
| **Supervisor or manager** | operator console | visibility into what was automated, refused and escalated, and why |
| **Judge (visitor)** | the public link | to see every path and the reasoning behind it within minutes |

## 2. Use cases

| ID | Use case | Expected behaviour |
|---|---|---|
| UC-1 | **Normal resolution** | Calvino identifies the request, the agent fetches the facts through tools, the verifiers pass the reply, and the customer sees a card with the verified answer |
| UC-2 | **Ambiguous request** | the decision falls in the uncertain band; the customer gets clarification choices, not a guess |
| UC-3 | **Unsupported request** | out of scope; an honest reply saying what Calvino can't do here, the right channel, and an offer to reach a person |
| UC-4 | **Human needed** | a hard rule, the decision classifier or a failed verification sends the case to a person with a complete case file; the customer is told what happens next |
| UC-5 | **Confirmed action** | a consequential action is shown as a card with a confirm button bound to that exact action; it runs only after confirmation and is reported only after it is verified |
| UC-6 | **Operator review** | an operator opens a case, sees the case file and the audit trail, and approves, edits or takes over |
| UC-8 | **Case follow-up** | days later the customer asks about their investigation; the case resumes from its saved state and the customer gets a verified status and next step |
| UC-9 | **Operator decisions improve the system** (offline) | operator approvals and denials become labels; a recalibrated policy version is replayed on the log, and the verdicts that change are shown |
| UC-7 | **Adversarial and failure cases** | prompt injection, another customer's data, expired session, tool failure, missing data and mixed language are refused or handled safely, and logged |

## 3. Functional requirements

| ID | Requirement | Use cases |
|---|---|---|
| FR-1 | Authenticate every conversation through a test session; never pass the session token to a model | all |
| FR-2 | Apply hard rules before any model-based decision; hard rules always win | UC-4, UC-7 |
| FR-3 | Decide the route (agents, human, out of scope) from calibrated scores and a versioned policy | UC-1 – UC-4 |
| FR-4 | Gate every tool call; consequential actions require a confirmation bound to the action | UC-5, UC-7 |
| FR-5 | Access bank data only through governed tools that check ownership | UC-1, UC-5, UC-7 |
| FR-6 | Verify every agent output against a rubric before the customer sees it; retry once, then escalate | UC-1, UC-4 |
| FR-7 | Show results as cards chosen from a fixed catalog, filled only from verified data: payment status, problem-payment picker, action confirmation (cancel or retry), action result, case opened, case status, handoff notice, out of scope | UC-1, UC-2, UC-5, UC-8 |
| FR-8 | Offer clarification choices when confidence is in the uncertain band | UC-2 |
| FR-9 | Produce a case file for every handoff: request, verified facts, actions taken, evidence, open questions | UC-4, UC-6 |
| FR-10 | Let operators approve, edit or take over a case, always through the Gate | UC-6 |
| FR-11 | Record every decision (inputs summary, scores, rule fired, verdict, versions) in the audit log | all |
| FR-12 | Show the reasoning behind each turn in a glass-box panel: scores, rules, tool results, verifier verdicts | all |
| FR-13 | Offer scenario shortcuts covering UC-1 to UC-5, UC-7 and UC-8, and a Spanish / Portuguese toggle | all |
| FR-14 | Keep cases durable: a case waiting for a person survives a restart and resumes with full state | UC-4, UC-8 |
| FR-15 | Replay the decision log under a new policy version and list the verdicts that change | UC-9 |

## 4. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-1 | **Privacy:** customer text for decisions stays with a self-hosted model; external models receive only redacted, minimal context |
| NFR-2 | **Explainability:** every verdict can be replayed from the audit log; explanations come from records, never hidden reasoning |
| NFR-3 | **Fairness:** outcome and error gaps by language, dialect, country and segment are measured and reported |
| NFR-4 | **Latency** `[hypothesis]`: a decision step adds well under a second on CPU; end-to-end p95 is reported per turn |
| NFR-5 | **Availability:** the public link stays reachable through the judging period, with a warm-up screen instead of a blank page |
| NFR-6 | **Safety under failure:** actions fail closed when a check can't run; model choice fails open to the more capable option |
| NFR-7 | **Cost:** cost per attempted case and per successful resolution are measured and bounded per case |
| NFR-8 | **Abuse protection:** the public demo has a rate limit, a spending cap on model keys and the confirmation key on writes |

## 5. Acceptance criteria

| ID | Given | When | Then |
|---|---|---|---|
| AC-1 | an authenticated customer with a clear, supported request | they ask in Spanish or Portuguese | they receive a verified answer card, and the audit log holds every decision for that turn |
| AC-2 | a request between two intents | it is classified in the uncertain band | clarification choices appear, and no action runs |
| AC-3 | a request outside the workflow | it is classified out of scope | an honest reply and a path to a person appear, and no agent starts |
| AC-4 | a hard-rule trigger (for example, the customer asks for a person) | the message arrives | the case goes to the operator queue with a complete case file, without any agent step |
| AC-5 | a consequential action | the customer has not confirmed it | it does not run; after confirmation it runs once and is reported only after a verified read-back |
| AC-6 | a request for another customer's data, or a prompt injection | it reaches a tool | it is refused, the rule is named, and the attempt is logged |
| AC-7 | an agent reply that states an amount not in the tool results | it is verified | it fails, is retried once, and escalates if it fails again |
| AC-8 | the same inputs and policy version | the decision is replayed from the log | the verdict is identical |

## 6. Dependencies and milestones

Phases, tiers and gates: [PLAN.md](PLAN.md). Work streams and their order: [ROADMAP.md](ROADMAP.md).
