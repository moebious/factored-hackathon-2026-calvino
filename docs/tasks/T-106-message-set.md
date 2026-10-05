# T-106: Team-generated customer message set

| | |
|---|---|
| Wave | 1 |
| Branch | `data/message-set` |
| Depends on | T-103; T-107 for gold-subset/oracle agreement |
| Blocked by | LLM provider keys (decision 28: the client exists, the tokens do not) |
| Model | standard model; the maintainer reviews a sample before use |
| Can run in parallel | no |
| References | decision 16; DESIGN.md 7, 8, 8.1; DATA.md findings |

**Goal.** Provide the customer text the classifiers are calibrated and evaluated on (and fine-tuned on, in Tier 1), since the dataset's transcripts are templated (decision 16).

**Inputs.** the label definitions and rubric from T-103; held-out records for the workflow (problem transactions, clean transactions, other customers' transactions, complaints) on synthetic personas, never copied customer records

**Outputs.** a versioned, labelled set of Spanish messages (Mexican, Colombian and Argentine variants) in disjoint training, calibration and held-out test splits, with generation prompts, review log and datasheet; all labelled synthetic. Reuse the outcome definitions and hand-written oracle already in `calvino.evaluation` (TSD-013), rather than create a competing oracle. T-303's committed 50-case suite stays frozen and unavailable to training, calibration, prompt/model selection or threshold tuning.

**Open parameters.** set size per split (state it); the LLM used to draft; the intents and outcomes follow DESIGN.md 6.1 and the oracle

**Done when.** every new test case has a seed record and an oracle outcome under the shared definitions; customer/time and prompt-generation separation is enforced, with adversarial rewordings and hand-written cases held out. A reviewed sample follows the rubric, no message duplicates a dataset transcript, and the existing T-303 suite is demonstrably absent from tuning data. Gold-subset/oracle agreement is measured on reviewed labels, not inferred from synthetic generation.

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
