# T-603: Offline verifier lab

| | |
|---|---|
| Wave | Tier 2 |
| Branch | `eval/verifier-lab` |
| Depends on | T-303 |
| Blocked by | — |
| Model | standard model |
| Can run in parallel | yes |
| References | DESIGN.md 4.4 |

**Goal.** Tune rubrics and judge prompts from traces.

**Inputs.** decision log disagreements; gold set

**Outputs.** a workflow that proposes and re-measures rubric changes

**Open parameters.** none

**Done when.** false-pass rate improves on the gold set, or the attempt is reported

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
