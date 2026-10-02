# T-301: Support agent and company brain

| | |
|---|---|
| Wave | 3 |
| Branch | `feat/support-agent` |
| Depends on | T-204, T-206 |
| Blocked by | LLM provider |
| Model | standard model |
| Can run in parallel | no |
| References | decision 15; DESIGN.md 4.0 |

**Goal.** The System 2 worker for the chosen workflow, grounded in tools and policy documents.

**Inputs.** the hub, the tools, policy documents for retrieval

**Outputs.** a Deep Agents worker; policy retrieval as a tool or subagent; prompts versioned

**Open parameters.** [workflow]

**Done when.** the verifier passes its outputs on the scripted scenarios in Spanish and Portuguese

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
