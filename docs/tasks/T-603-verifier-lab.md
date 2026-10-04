# T-603: Offline verifier lab

| | |
|---|---|
| Wave | Core verifier evidence (decision 35) |
| Branch | `eval/verifier-lab` |
| Depends on | T-303 |
| Blocked by | — |
| Model | standard model |
| Can run in parallel | yes |
| References | DESIGN.md 4.4 |

**Goal.** Provide a reproducible offline benchmark for financial verifier false passes, disagreements and regressions. People author rubric changes; no agent edits its own rubric.

**Inputs.** decision log disagreements; gold set

**Outputs.** labelled financial mistakes, criterion-level disagreement ledger, repeatable false-pass/false-fail measurements and a report comparing human-authored code-check or checklist revisions on development and untouched promotion sets

**Open parameters.** none

**Done when.** the existing verifier and one human-authored proposed revision are evaluated against the same labelled cases, with false passes, false fails, cost and sample sizes; a rejected or unchanged proposal is reported. Repeatedly tuning on the frozen set is forbidden.

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
