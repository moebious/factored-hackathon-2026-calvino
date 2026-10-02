# Brief coverage

*Every requirement in the hackathon brief, mapped to where Calvino addresses it and how it is evidenced. "Designed" means specified in the docs; "built" and "measured" are updated as tasks land.*

Status: **designed** · **built** · **measured** · **gap**.

## Core ask

| Brief asks | Where | Evidence (task) | Status |
|---|---|---|---|
| Understand complex interactions | DESIGN 2, 4.2–4.3 (System 1 + System 2) | T-201, T-303 | designed |
| Use data and tools securely | DESIGN 4.0, 5.2; TSD-002 | T-002 security tests | designed |
| Complete service workflows | DESIGN 4, 6; PRD UC-1, UC-5 | T-204, T-301 | designed |
| Involve human agents when needed | DESIGN 2 (System 3), 4.2, 6; PRD UC-4, UC-6 | T-204, T-302 | designed |
| A focused problem, why it matters, a baseline | TSD-006; BRD 2–3 | T-101, T-104 | designed (rule fixed, data pending) |
| Improvement in service quality and operational efficiency | BRD 3; DESIGN 7 | T-303 | designed |

## Think beyond the demo

| Brief asks | Where | Status |
|---|---|---|
| Privacy, explainability, fairness, reliability, scalability | DESIGN 5, 5.1–5.3 | designed |
| Trade-offs across autonomy, accuracy, latency, cost, oversight | DESIGN 5 (threshold frontier by expected cost), 4.4 (risk tiers) | designed |
| Where AI fits, where deterministic logic is better | DESIGN 2–3 (Systems 1 → 3, the who-does-what matrix) | designed |
| How quality and safety are evaluated | DESIGN 4.4, 7 | designed |

## Scope

| Brief asks | Where | Evidence | Status |
|---|---|---|---|
| Working prototype, production readiness, honest remaining work | PLAN; DESIGN 4.0.2, 9 | T-304, T-501 | designed |
| One coherent workflow, depth over breadth | TSD-006; PLAN ladder | T-101 | designed |
| Normal path / ambiguous or unsupported / human intervention | PRD UC-1 to UC-4, AC-1 to AC-4 | T-204, T-205 | designed |
| Spanish and Portuguese, limitations reported | DESIGN 5.1, 8.1 | T-203, T-303 | designed |

## What the solution should demonstrate

| # | Brief asks | Where | Evidence | Status |
|---|---|---|---|---|
| 1 | Contact reasons, demand, data quality, constraints | TSD-006; DESIGN 8 | T-101, T-102 | designed |
| 2 | Context, clarification, grounded answers, verified actions only | DESIGN 4.4; PRD FR-6 to FR-8 | T-204, T-301 | designed |
| 3 | Answer / confirm / abstain / transfer; policy outside the model; handoff packet | DESIGN 2, 4.1–4.2; PRD FR-2 to FR-4, FR-9 | T-001, T-204, T-302 | designed |
| 4 | Contracts, quality checks, lineage, freshness; learned component vs baseline; labels, leakage, thresholds, splits | DESIGN 7, 8.2 | T-102, T-103, T-105, T-201 | designed |
| 5 | Held-out evaluation with failure cases; outcomes, latency, cost | DESIGN 7; PRD AC-6, AC-7 | T-303 | designed |
| 6 | Tracing, bounded retries, safe fallback, reproducible setup; capacity, monitoring, access, retention; explanations from records | DESIGN 4.1, 5.3, 9 | T-204, T-501 | designed |

## Architecture freedom, data boundaries, evaluation evidence

| Brief asks | Where | Status |
|---|---|---|
| Data engineering and ML rigour for pretrained components (selection, labels, representations, leakage, held-out evaluation, error analysis) | DESIGN 4.3, 7 | designed |
| Static data: demonstrate update correctness with a labelled fixture | DESIGN 8.2; T-105 | designed |
| State what is real, synthetic, team-generated | DESIGN 8.1 | designed |
| No private data in external model requests | DESIGN 5.2 | designed |
| Mock tools with documented contracts; trusted test session; access enforced in the tool layer | TSD-002; DESIGN 5.2 | designed |
| Baseline and system on the same held-out workload; case mix, label quality, versions, repeated-run variability; failures included | DESIGN 7 | designed |
| LLM judge: rubric documented and validated against human judgments | DESIGN 4.4 | designed |
| Safe automated resolution (+ attempt rate), containment, escalation quality, unsafe outcomes, p50/p95 latency and cost per case and per resolution | DESIGN 7; BRD 3 | designed |
| Outcomes by language and segment; small-sample limits; offline vs simulated vs projected | DESIGN 5.1, 7 | designed |

## Submission deliverables

| Deliverable | Task | Status |
|---|---|---|
| Public repository `factored-hackathon-2026-[team]` | done | built |
| Deployed working link | T-304 | designed |
| 4–6 slides | T-503 | designed |
| Video of 3 minutes or less | T-504 | designed |
