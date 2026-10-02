# Project Calvino: Business Requirements Document (BRD)

*Why Calvino exists: the problem, the goals, what is in and out of scope. What the product does is in [PRD.md](PRD.md); how it is designed is in [DESIGN.md](DESIGN.md).*

## 1. Executive summary

Banks want AI to resolve customer requests, but a model on its own can't be trusted to decide what it may do, whether its answer is grounded, or when a person must take over. Calvino is a domain-specific harness that makes those decisions explicit, governed and measurable, so a bank can automate what is safe, involve people where accountability is required, and prove both.

Context: Factored AI & Data Hackathon 2026, "Build an AI-first banking customer service system", on a synthetic LATAM bank dataset (Mexico, Colombia, Argentina).

## 2. Problem

- Customer service demand is high and repetitive, yet a share of contacts needs judgment, verification or accountability that automation alone can't provide.
- Fully automated assistants fail in two costly ways: **unsafe outcomes** (wrong answers, unauthorized disclosures or actions) and **unnecessary escalations** (human time spent on cases that didn't need it).
- Decisions made inside model prose can't be audited, replayed or explained to a regulator.
- Customers write in regional Spanish and in Portuguese, and service quality must not depend on who they are or how they speak.

The workflow is stuck payments: payments and transfers that are Declined, Pending or Reversed, from the first question to the investigation and its follow-up (decision 17). Transaccional is the largest contact category (35% of calls) and 8% of transactions end in one of those statuses `[measured]`.

## 3. Business goals and KPIs

| Goal | KPI (as defined in the brief) |
|---|---|
| Resolve eligible cases safely without a person | **Safe automated resolution rate** over all in-scope cases, plus the share where automation was attempted |
| Keep cases out of the human queue only when they are actually solved | **Containment**, reported alongside resolution, never alone |
| Send people the cases that need them, with what they need | **Escalation quality**: missed and unnecessary transfers; completeness of the handoff |
| Never act or disclose unsafely | **Unsafe outcomes**, with counts and denominators |
| Serve efficiently | **p50 / p95 latency**; **cost per attempted case** and **per successful automated resolution** |
| Serve everyone equally well | outcome and error gaps by language, dialect, country and segment |

Every KPI is compared against the **human baseline** from the dataset (resolution, escalation and handle time) on the same held-out cases.

## 4. Scope

**In scope**

- One focused customer service workflow, chosen from the data, built end to end.
- The normal resolution path, ambiguous and unsupported requests, and cases requiring human intervention.
- Spanish (Mexican, Colombian, Argentine) and Portuguese interactions.
- A deployed, working demo, an evaluation report, and an honest account of the work left before production.

**Out of scope**

- Live banking: no real money movement, lending decisions or real customer data.
- More than one workflow built in depth (others are documented only).
- Production identity, data residency and real bank-core integration (documented as production work).

## 5. Stakeholders

| Stakeholder | Interest |
|---|---|
| Bank customers | fast, correct, respectful service in their language |
| Human agents and supervisors | fewer, better-prepared escalations; control over consequential actions |
| Operations managers | cost, capacity and quality they can see and steer |
| Risk, compliance and audit | decisions that can be explained, replayed and governed |
| Hackathon judges | technical judgment, AI and data engineering, ML and analytics rigour |

## 6. Constraints

- Only organizer-approved, synthetic data; inputs labelled as real, synthetic or team-generated; no private data in external model requests.
- Authentication through a trusted test session; access enforced in the tool layer.
- Four deliverables: public repository, deployed link, 4–6 slides, a video of 3 minutes or less.

## 7. Assumptions and risks

| Assumption or risk | Response |
|---|---|
| The synthetic labels reflect what agents did, not what was needed | a hand-labelled gold set and reported agreement |
| Open models may underperform on Spanish and Portuguese | calibration, fine-tuning, and a simpler learned baseline as fallback |
| No Portuguese in the dataset | a clearly labelled synthetic Portuguese test set, with the limitation reported |
| Scope grows beyond what can be finished | the tier ladder and its gates in [PLAN.md](PLAN.md) |
