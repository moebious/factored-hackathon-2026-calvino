# Pitch

*Outline for the 4–6 slides and the video of 3 minutes or less. Numbers marked `[result]` are filled in from the evaluation (T-303); until then they are placeholders, never claims.*

## The one line

> **Laya is System 1, Calvino is System 1.5, agents are System 2, and humans are System 3.**
> Calvino decides who should act, checks what agents produce, and learns from every human decision, so a bank can automate what is safe and prove it.

## Slides

| # | Slide | Content | Evidence shown |
|---|---|---|---|
| 1 | **The problem** | Customer service in a LATAM bank: demand concentrated in [workflow]; today's resolution and escalation rates; what unsafe automation and unnecessary escalation cost | contact-reason chart and the human baseline `[result]` (T-101, T-104) |
| 2 | **The idea** | Agent = Model + Harness; Calvino as the hub; the four systems as an escalation ladder; probabilities in, deterministic verdicts out | the architecture diagram |
| 3 | **How it stays safe** | Hard rules first; calibrated thresholds chosen by expected cost; Gate before every action; verifier cascade with rubrics; humans with a complete case file | the threshold frontier, judge false-pass rate `[result]` |
| 4 | **Results** | Safe automated resolution and attempt rate, containment, escalation quality, unsafe outcomes, latency and cost per case, by language | results table `[result]` (T-303), labelled offline / simulated |
| 5 | **Engineering** | Data contracts and quality report, leakage-free splits, Laya vs baselines, MCP with ISO 20022-aligned contracts, spec-driven build with CI-enforced conventions | quality report, classifier table `[result]` |
| 6 | **What's next** | The production route (AWS VPC, bank-core adapters, identity), the flywheel, verification as a product; honest remaining work | production-gap list |

Rule for every slide that names a layer: **show that layer's number.** Without numbers the framework reads as branding.

## Video beat sheet (3:00)

| Time | Beat | On screen |
|---|---|---|
| 0:00–0:20 | The problem in one sentence and one number | contact-reason chart |
| 0:20–0:45 | The idea: four systems, Calvino as the hub | architecture diagram |
| 0:45–1:30 | **Live demo, Spanish:** a normal request resolved with a verified card, then an ambiguous one with clarification chips | customer app + glass box showing scores and rules |
| 1:30–1:55 | **Live demo, Portuguese:** a case a hard rule sends to a person; the operator opens the case file and approves | operator console, audit timeline naming the rule |
| 1:55–2:15 | **Safety moment:** a prompt injection or another customer's data, refused and logged | glass box: refusal with rule id |
| 2:15–2:45 | Results: three numbers, labelled offline | results table |
| 2:45–3:00 | Close: the one line, the link | `calvino.rubrica.dev` |

## Phrases to keep

- "Probabilities in, deterministic verdicts out."
- "System 3 teaches System 1."
- "We bound and measure non-determinism; we don't claim to remove it."
- "The demo runs on a dataset adapter; production swaps the adapter, not the agent."
- "Inspired by Kahneman; Systems 1.5 and 3 are our engineering extensions."

## Avoid

- Calling offline comparisons production improvements.
- Claiming ISO 20022 compliance (it is "aligned").
- Showing vendor benchmark numbers as our results.
- Over-claiming novelty for Systems 1 and 2; the novelty is System 1.5, the financial verifiers and the governed flywheel.
