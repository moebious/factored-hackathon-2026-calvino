# T-301: Support agent and company brain

| | |
|---|---|
| Wave | 3 |
| Branch | `feat/support-agent` |
| Depends on | T-204, T-206 |
| Blocked by | LLM provider keys (decision 27: the client exists, the tokens do not) |
| Model | standard model |
| Can run in parallel | no |
| References | decision 15; DESIGN.md 4.0 |

**Goal.** The System 2 worker for the chosen workflow, grounded in tools and policy documents.

**Inputs.** the hub, the tools, policy documents for retrieval, the playbook `playbooks/stuck-payments.yaml` (decision 24); the agent's model is an open Qwen model (decision 20)

**Outputs.** a Deep Agents worker; policy retrieval as a tool or subagent; prompts versioned

**Open parameters.** the agent prompts for the explain, clarify, act and follow-up stages (DESIGN.md 6.1)

**Done when.** the verifier passes its outputs on the scripted scenarios in Spanish and Portuguese

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
