# Glossary

| Term | Meaning in Calvino |
|---|---|
| **Calvino** | the domain-specific harness: the hub every request, action and decision passes through. Named after Italo Calvino's *Invisible Cities* |
| **Harness** | everything around a model that makes it useful and safe: tools, state, policy, verification, logging ("Agent = Model + Harness") |
| **System 1** | Laya: fast, non-generative, repeatable typed decisions with calibrated probabilities |
| **System 1.5** | the Calvino hub: turns System 1 signals into deterministic verdicts, routes work, gates actions, verifies, records |
| **System 2** | the generative agents (support chat, company brain, coworker) and the verifiers that contain them |
| **System 3** | humans: accountable judgment, the final authority |
| **Escalation ladder** | each system up is slower, costlier and holds more responsibility; a case is resolved at the lowest system that can do it safely |
| **Hub and spoke** | Calvino at the center; channels, agents, humans, models and bank integrations are spokes that only communicate through the hub |
| **Communicating vessels** | the methodology's image: isolated environments exchange state only through contracts (case file, decision log, tool contracts) |
| **Laya** | the open-weight System One model (Convai Innovations, Apache 2.0) used for typed decisions |
| **Typed questions** | `choice`, `score` and `noul` (yes/no) questions answered with probabilities in one forward pass |
| **Calibration** | making a probability mean what it says (a 0.7 is right about 70% of the time); done with temperature scaling per question type |
| **Hard rules** | deterministic rules (fraud signal, amount limit, request for a person…) that run before any model and always win |
| **Decision classifier** | classification layer 1: decides whether agents take charge, a human is needed, or the request is out of scope |
| **Human intervention classifier** | the part of the decision classifier that decides whether and how to involve a person: none, approve an action, request information, full transfer |
| **Gate** | the check before every tool call: allow, ask, or block; fails closed |
| **Policy** | the versioned, unit-tested configuration of thresholds and rules that turns scores into verdicts |
| **Verifier cascade** | classification layer 2: code checks, then Laya, then one batched LLM-judge call over a rubric |
| **Rubric** | a versioned list of pass/fail criteria for one kind of agent output |
| **Mixture of financial verifiers** | the verifiers as a whole, including the specialist panel used for high-risk actions |
| **False pass** | a verifier passing an output that should fail; the error the verifiers are optimised against |
| **Case file** | the only handoff format: request, verified facts, actions taken, evidence, open questions |
| **Decision log** | `decisions.jsonl`: every decision with inputs summary, scores, rule fired, verdict and versions; the source of explanations and replay |
| **Data flywheel** | human decisions become gold labels that recalibrate System 1 and tune the verifiers ("System 3 teaches System 1"), with safeguards |
| **Glass box** | the demo panel that shows scores, rules, tool results and verifier verdicts behind each turn |
| **MCP adapter** | the component that connects the hub's tools to one bank core (a dataset adapter for the demo) |
| **ISO 20022-aligned** | tool payloads shaped after ISO 20022 messages (camt, pacs) without claiming full compliance |
| **Evidence labels** | `[measured]`, `[vendor]`, `[read from chart]`, `[hypothesis]` on claims in the docs |
| **Result labels** | offline (held-out data), simulated (scripted conversations), projected (business estimate) |
| **Tier 0 / 1 / 2** | the build ladder: submittable core, depth, integration standards |
| **Stuck payment** | a payment or transfer that is Declined, Pending or Reversed: the workflow Calvino serves (decision 17) |
| **Problem transaction** | a transaction in one of those statuses; 8.0% of the dataset |
| **Seeded oracle test set** | test cases that each start from a held-out record and carry the expected outcome computed by a hand-written table (the oracle), so outcomes are scored exactly |
| **Bare-LLM ablation** | the same adversarial cases run through an LLM without the harness, to measure what Calvino adds |
| **False-pass rate** | the share of failing outputs a verifier lets through, measured against hand labels |
| **Policy replay** | re-running the decision log under a new policy version to see which verdicts change |
| **Pilot window** | the analyst's two-week development subset (17–30 June 2023); never the source of a published number |
| **BRD / PRD / TSD** | business requirements (why), product requirements (what), technical specification (how one part is built) |
