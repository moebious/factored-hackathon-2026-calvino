# References

*The sources that shaped Calvino: a short summary of each, what we took from it, and where it shows up. Summaries are our own paraphrase; consult the originals for detail. Figures quoted from sources are vendor claims unless we reproduced them.*

## Hackathon

**Factored AI & Data Hackathon 2026, problem statement** (organizers' PDF).
Build an AI-first banking customer service system for one focused workflow; show a problem supported by data, a functioning AI system, controlled automation, sound data and ML practice, measured quality and failure handling, and a credible route to operation. Requires Spanish and Portuguese, a baseline, held-out evaluation and specific outcome metrics.
→ The whole project; see [BRIEF-COVERAGE.md](../BRIEF-COVERAGE.md).

**Hackathon page** (https://www.factored.ai/careers/ai-data-hackathon).
Four deliverables (public repository, deployed link, 4–6 slides, video of 3 minutes or less) and five judging dimensions (technical judgment, AI engineering, data engineering, machine learning, data analytics), "quality over quantity".
→ PLAN.md deliverables; T-304, T-503–T-505.

**LATAM Bank dataset summary and data dictionary** (organizers' PDFs).
→ [DATA.md](../DATA.md).

## Harness engineering

**V. Trivedy, *The Anatomy of an Agent Harness*, LangChain, 2026-03-10.**
Agent = Model + Harness: everything that isn't the model (prompts, tools, environment, orchestration, hooks, memory, verification). Harness features are derived by working backwards from the behaviour you want.
→ The core framing; Calvino is a domain-specific harness.

**S. Runkle, H. Lovell, *Building a Harness with Jev*, LangChain, 2026-09-17.**
A "System One" model returns typed answers with probabilities instead of text, cheaply and fast, so decisions inside an agent loop (model routing, gating risky tool calls) don't need a full LLM call.
→ System 1 and the Gate.

***Building a Custom Harness with Pi and Jev*** (DAIR.AI Academy).
A custom harness with three decision points: a router (pick the model once per request), a gate before tool calls (two thresholds: allow, ask a human, block), and a verifier for the final answer; thresholds kept in one testable policy function; fail closed for the gate, fail open for the router; check in code whatever code can check; log every decision with its numbers.
→ DESIGN 4.1 (the three checkpoints), the policy engine (TSD-001), the decision log.

**Anthropic, *Harness design for long-running application development*.**
Separate the agent doing the work from the one judging it; hand work over through structured artifacts rather than long transcripts; agree what "done" means before starting; every harness component encodes an assumption worth testing and removing when models improve.
→ Independent verifiers, the case file, definitions of done, ablations in the evaluation plan.

**LangChain Labs and Harvey, *Designing Efficient Verifiers for Legal Agents*, 2026-06-02.**
Rubric-based verification with one pass/fail verdict per criterion; batching the whole rubric in one call is about ten times cheaper with somewhat lower agreement; open models can approach a frontier reference far more cheaply while some cheap models are far too lenient; frontier judges agree only about 95.7% with each other; prompting the judge to decompose criteria into a checklist and to fail when unclear lowers false passes.
→ DESIGN 4.4 (verifier cascade, false-pass optimisation, judge validation), TSD-004.

## System One model

**Laya** (https://huggingface.co/convaiinnovations/laya, Apache 2.0).
Open-weight, non-generative decision models (an English and a multilingual checkpoint, plus a fine-tuned typed-decisions one) answering typed questions with probabilities in one forward pass; trained for calibration. Its own documentation states the limits: near chance on typed decisions without fine-tuning, over-confident until temperatures are refit on your data, weak on score questions and on many-option choices, yes/no answers can follow their labels, an unusable `act_probability`, weaker routing on the multilingual checkpoint, and an English checkpoint that fails on non-Latin scripts.
→ DESIGN 4.3 (usage rules), TSD-005; our own CPU smoke test in DESIGN 4.3.

## Interfaces

**Shapeshift** (https://github.com/anishfn/shapeshift).
A text box that becomes a UI card: a System One model answers many typed questions at once to pick a card from a fixed catalog, deterministic parsers fill it, uncertain picks show "did you mean" choices, a small state machine prevents flicker, and an offline keyword classifier is the fallback.
→ The customer app's Laya-chosen cards (decision 10).

**OpenBot** (https://github.com/CopilotKit/openbot, MIT).
AI coworkers whose every action passes one policy gateway that fails closed and is recorded (permitted, refused, failed, with the rule that refused it), with a console to watch and take control. Also connects agents over AG-UI. Its per-agent computers and sandboxes are heavy and alpha.
→ The Calvino Console's philosophy (decision 11); the machinery was rejected.

**CopilotKit / AG-UI, OpenDots, OpenMuse.**
AG-UI is a protocol for agent-to-interface communication; the templates are UX layers over similar agent cores. OpenMuse with a System One model shows "clickable choices instead of a wall of text".
→ Tier 2 (AG-UI endpoint, CopilotKit console); validation for the card UI.

## Standards and methods

**ISO 20022** (financial messaging).
Message families for payments and cash management, e.g. account statements and notifications (camt.053 / camt.054), payment status (pacs.002), investigations (camt.027 / camt.029). Cards still largely use ISO 8583.
→ ISO 20022-aligned tool contracts (decision 12).

**Conventional Commits 1.0.0; Git best practices; Git worktrees** (conventionalcommits.org; daily.dev; dev.to "Git worktree like a boss").
→ AGENTS.md git workflow (decisions 7 and 8).

**BRD, PRD, SDD and TSD** (article on software documentation types).
Business requirements (why), product requirements (what), software design (how it is designed), technical specification (how each part is built).
→ BRD.md, PRD.md, DESIGN.md, specs/.

**Italo Calvino, *Invisible Cities*.**
Self-contained cities known to the Khan only through Marco Polo's accounts.
→ The name and the hub-and-spoke metaphor.

## To read

***Fairness in Generative AI*** (Packt). Not yet used as a source.
