# T-301: Bounded support agent with policy retrieval

| | |
|---|---|
| Wave | 3 |
| Branch | `feat/support-agent` |
| Depends on | T-204, T-206 |
| Blocked by | LLM provider keys (decision 28: the client exists, the tokens do not) |
| Model | standard model |
| Can run in parallel | no |
| References | decision 15; DESIGN.md 4.0 |

**Goal.** The bounded generative System 2 worker for stuck payments, grounded in governed tools, the versioned playbook and policy retrieval; the model proposes, but never authorizes.

**Inputs.** the hub, the tools, policy documents for retrieval, the playbook `playbooks/stuck-payments.yaml` (decision 24); the agent's model is an open Qwen model (decision 20)

**Outputs.** one support-agent implementation of the hub's existing `SupportAgent` interface, policy retrieval with cited evidence, versioned prompts, redacted provider inputs, and Spanish and Portuguese replies under the verifier. A separate company-brain agent is not required.

**Open parameters.** the agent prompts for the explain, clarify, act and follow-up stages (DESIGN.md 6.1)

**Done when.** the live worker's Spanish and Portuguese outputs pass the verifier on seeded scenarios, its tool calls are limited by stage and the Gate, model-visible arguments carry no session token, and failures escalate with evidence. T-303 separately measures repeated-run variability and unsafe outcomes.

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
