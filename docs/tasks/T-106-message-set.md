# T-106: Team-generated customer message set

| | |
|---|---|
| Wave | 1 |
| Branch | `data/message-set` |
| Depends on | T-103 |
| Blocked by | LLM provider keys (decision 28: the client exists, the tokens do not) |
| Model | standard model; the maintainer reviews a sample before use |
| Can run in parallel | no |
| References | decision 16; DESIGN.md 7, 8, 8.1; DATA.md findings |

**Goal.** Provide the customer text the classifiers are calibrated and evaluated on (and fine-tuned on, in Tier 1), since the dataset's transcripts are templated (decision 16).

**Inputs.** the label definitions and rubric from T-103; held-out records for the workflow (problem transactions, clean transactions, other customers' transactions, complaints) on synthetic personas, never copied customer records

**Outputs.** a versioned, labelled set of Spanish messages (Mexican, Colombian and Argentine variants) for training, calibration and test, with the generation prompts, the review log and a datasheet; all labelled synthetic. **Test cases are seeded:** each one names the record it starts from and carries the expected outcome computed by the oracle (DESIGN.md 7), a deterministic table written by hand and kept separate from the hub's policy code

**Open parameters.** set size per split (state it); the LLM used to draft; the intents and outcomes follow DESIGN.md 6.1 and the oracle

**Done when.** every test case has a seed record and an oracle outcome; the oracle has unit tests and its agreement with the hand-labelled gold subset is reported; train and test come from separate generation prompts; the test split includes adversarial rewordings and a hand-written subset; a reviewed sample shows the labels follow the rubric; a check confirms no message duplicates a dataset transcript

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
