# T-303: End-to-end evaluation

| | |
|---|---|
| Wave | 3 |
| Branch | `eval/end-to-end` |
| Depends on | T-301, T-203 |
| Blocked by | — |
| Model | strong model or maintainer review (judgment checkpoint) |
| Can run in parallel | no |
| References | DESIGN.md 7; BRD 3 |

**Goal.** Produce the brief's evidence.

**Inputs.** the running system; held-out cases; the Portuguese set; adversarial cases

**Outputs.** safe automated resolution and attempt rate, containment, escalation quality, unsafe outcomes, p50/p95 latency and cost per case and per resolution; repeated runs; judge validation; error analysis; by language and segment

**Open parameters.** none

**Done when.** results labelled offline / simulated / projected, with sample sizes and limitations, in the README and a report

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
