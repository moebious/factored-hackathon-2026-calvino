# T-502: Release notes and tags

| | |
|---|---|
| Wave | 5 |
| Branch | `docs/release` |
| Depends on | T-501 |
| Blocked by | maintainer approval |
| Model | standard model |
| Can run in parallel | yes |
| References | AGENTS.md versioning |

**Goal.** Package a final, reviewable submission release; do not manufacture missing intermediate milestone tags.

**Inputs.** CHANGELOG

**Outputs.** a final changelog and, with maintainer approval, an annotated submission tag and release. Model, policy and rubric versions remain governed separately by T-407/T-408, not by this packaging step.

**Open parameters.** none

**Done when.** the final state is reproducibly identified, the changelog describes what actually shipped and the optional final release is published with the maintainer's approval. Backfilling milestone releases is not a submission gate.

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
