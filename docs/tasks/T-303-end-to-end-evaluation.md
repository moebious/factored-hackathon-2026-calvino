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

**Inputs.** the running system; the seeded test set with oracle outcomes (T-106); the Portuguese set; adversarial cases

**Outputs.** safe automated resolution and attempt rate, containment, escalation quality, unsafe outcomes, p50/p95 latency and cost per case and per resolution; repeated runs; judge validation with the verifier's false-pass rate on hand labels; a bare-LLM ablation on the same adversarial set (unsafe outcomes, bare vs Calvino); error analysis; by language and segment; compared with both baselines (Transaccional calls, Transactions-category complaints). On calls the target is to match the human first-contact resolution of 91.5% `[measured]` with zero unsafe outcomes, at lower latency and cost; investigation time savings are reported as projected only

**Must include** (from the brief): incorrect or missing data, expired sessions, unauthorized access attempts, prompt injection, tool failures and multilingual ambiguity; the edge cases in DESIGN.md 6.1 (exchange-rate discrepancy, hostile message about a trivial fee, empty or garbled messages); the model and prompt versions of every run; repeated-run variability; latency as model compute and as end-to-end time after a discarded warm-up; calibration per language (decision 25) and at least the dialect and language flip table; the judge's false-pass rate for a judge from another family than the agent (decision 20). The acceptance scenarios (decision 23) are the first slice of the test set.

**Open parameters.** none

**Done when.** outcome metrics are scored against the oracle outcomes, with the oracle's agreement with the gold subset reported; results labelled offline / simulated / projected, with sample sizes and limitations, in the README and a report

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
