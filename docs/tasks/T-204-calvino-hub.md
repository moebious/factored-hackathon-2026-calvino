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

**Goal.** Wire System 1.5: identity → hard rules → decision classifier → Gate → verification → case file, with a human interrupt.

**Inputs.** the policy engine, MCP tools, verifier and Laya client

**Outputs.** a LangGraph graph with the checkpointer, `interrupt()` for human steps, every decision logged

**Open parameters.** [workflow] routes and questions

**Done when.** end-to-end tests with fakes cover the normal, ambiguous, out-of-scope and human-needed paths (PRD AC-1 to AC-4)

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
