# T-204: Calvino hub

| | |
|---|---|
| Wave | 2 |
| Branch | `feat/hub` |
| Depends on | T-001, T-002, T-004, T-005 |
| Blocked by | — |
| Model | strong model or maintainer review (judgment checkpoint) |
| Can run in parallel | no |
| References | DESIGN.md 2, 4; PRD FR-1 to FR-11 |

**Goal.** Wire System 1.5 for the stuck-payments workflow (decision 17): identity → hard rules → Laya → policy verdict → tools → agent → verification, with the clarify, act (Gate), investigate (human interrupt and case file) and follow-up (resume) stages.

**Inputs.** the policy engine, MCP tools, verifier and Laya client

**Outputs.** a LangGraph graph with the checkpointer, `interrupt()` for human steps, every decision logged

**Open parameters.** none: the five stages and Laya's questions are in DESIGN.md 6.1

**Constraints.** per-stage tool lists and the playbook file (decision 24); a trusted test session issued by the hub for each persona, never a customer number typed in chat; per-language thresholds once `policy/v2` exists (decision 22)

**Done when.** end-to-end tests with fakes cover the normal, ambiguous, out-of-scope and human-needed paths, and the acceptance scenarios for AC-1 to AC-4, AC-6 and AC-8 pass in CI (decision 23)

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
