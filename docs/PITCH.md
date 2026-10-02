# Pitch

*Outline for the 4–6 slides and the video of 3 minutes or less. Numbers marked `[result]` are filled in from the evaluation (T-303); until then they are placeholders, never claims.*

## The one line

> **Calvino is an evolutionary, AI-powered decision engine for banking customer service: it answers payment questions safely, takes an action only when the policy allows it, and hands investigations to people with a complete file.**
> Decision engine: every consequential choice is a verdict from a versioned, deterministic policy. AI-powered: Laya's calibrated probabilities and an LLM's checked replies feed it without deciding. Evolutionary: people's decisions become labels, and each improvement ships as a new policy version after replay and evaluation. Laya is System 1, Calvino is System 1.5, agents are System 2, and humans are System 3.

## Slides

| # | Slide | Content | Evidence shown |
|---|---|---|---|
| 1 | **The problem** | Customer service in a LATAM bank: demand concentrated in stuck payments (35% of calls transactional, 8% of transactions declined, pending or reversed). The calls are high-volume and easy (humans resolve 91.5% on first contact), so automation must **match** people with zero unsafe outcomes at lower time and cost; the slow part is investigations (74.5% of transaction complaints still open, a median of 15 days to resolve) | contact-reason chart and the human baseline (T-101, T-104) `[measured]`, after comparison with the analyst's figures |
| 2 | **The idea** | Agent = Model + Harness, and in Calvino the harness, not the model, owns every consequential decision: the Router decides who acts, the Gate decides whether an action may run, the model can propose but never authorize. Calvino as the hub; the four systems as an escalation ladder | the architecture diagram |
| 3 | **How it stays safe** | Hard rules first; calibrated thresholds chosen by expected cost; Gate before every action (allow, ask, block); verifier cascade with rubrics; humans with a complete case file | the threshold frontier, the verifier's false-pass rate, unsafe outcomes bare LLM vs Calvino `[result]` |
| 4 | **Results** | Safe automated resolution and attempt rate, containment, escalation quality, unsafe outcomes, latency and cost per case, by language, scored against a seeded oracle and both human baselines | results table `[result]` (T-303), labelled offline / simulated |
| 5 | **Engineering** | The data-quality findings (templated text, links at chance), contracts, leakage-free splits, Laya vs baselines, MCP with ISO 20022-aligned contracts, spec-driven build with CI-enforced conventions | quality report, classifier table `[result]` |
| 6 | **What's next** | The production route (AWS VPC, bank-core adapters, real identity, data residency; other bank systems calling Calvino through MCP), agents earning autonomy one measured, signed policy version at a time, verification as a product. Honest limits: the core is simulated and no money moves; customer text and the Portuguese set are synthetic; time savings on investigations are projected | production-gap list |

Rule for every slide that names a layer: **show that layer's number.** Without numbers the framework reads as branding.

## Video beat sheet (3:00)

| Time | Beat | On screen |
|---|---|---|
| 0:00–0:20 | The problem in one sentence and two numbers: people already resolve 91.5% of these calls, but investigations stay open for weeks | contact-reason chart and baseline |
| 0:20–0:45 | The idea: four systems, Calvino as the hub | architecture diagram |
| 0:45–1:30 | **Live demo, Spanish:** "my transfer didn't arrive" explained from the record with a verified card; then "a payment disappeared", clarified with the problem-payment picker; then a pending transfer cancelled under the Gate | customer app + glass box showing scores, rules and the Gate verdict |
| 1:30–1:55 | **Live demo, Portuguese:** a cancellation above the limit goes to a person; the operator approves from the case file; later the customer asks about the case and gets a verified status | operator console, audit timeline naming the rule |
| 1:55–2:15 | **Safety moment:** asking about another customer's transfer, and a prompt injection, both refused and logged; the same cases through a bare LLM | glass box: refusal with rule id; the ablation number |
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
- Unmeasured figures (for example "33 ms" or F1 scores from planning drafts); every number carries its evidence label.
- Calling the judge or the panel the decision maker: decisions come from Laya's probabilities and the policy; the judge only checks language, and the panel can only veto.
- "It evolves itself": it improves from human decisions, under version control, with replay and evaluation before each change.
- Roles mixed up: an operator approves actions the Gate sends to a person; a supervisor sees what was automated and audits a sample; disputes and fraud always go to a person.
