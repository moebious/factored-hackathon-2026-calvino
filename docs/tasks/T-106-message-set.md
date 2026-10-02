# T-106: Team-generated customer message set

| | |
|---|---|
| Wave | 1 |
| Branch | `data/message-set` |
| Depends on | T-103 |
| Blocked by | LLM provider |
| Model | standard model; the maintainer reviews a sample before use |
| Can run in parallel | no |
| References | decision 16; DESIGN.md 7, 8, 8.1; DATA.md findings |

**Goal.** Provide the customer text the classifiers are calibrated, fine-tuned and evaluated on, since the dataset's transcripts are templated (decision 16).

**Inputs.** the label definitions and rubric from T-103; dataset scenarios for the chosen workflow (personas, transactions, complaints), read as aggregates or synthetic personas, never copied customer records

**Outputs.** a versioned, labelled set of Spanish messages (Mexican, Colombian and Argentine variants) for training, calibration and test, with the generation prompts, the review log and a datasheet; all labelled synthetic

**Open parameters.** [workflow] intents and scenarios; set size per split (state it); the LLM used to draft

**Done when.** train and test come from separate generation prompts; the test split includes adversarial rewordings and a hand-written subset; a reviewed sample shows the labels follow the rubric; a check confirms no message duplicates a dataset transcript

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
