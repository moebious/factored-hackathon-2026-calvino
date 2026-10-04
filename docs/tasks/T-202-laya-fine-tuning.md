# T-202: Laya fine-tuning on Kaggle

| | |
|---|---|
| Wave | Core thesis proof (decision 34 supersedes decision 17's Tier 1 placement) |
| Branch | `eval/laya-finetune` |
| Depends on | T-106 |
| Blocked by | GPU (maintainer runs the notebook) |
| Model | standard model |
| Can run in parallel | yes |
| References | DESIGN.md 4.0.1 |

**Goal.** Demonstrate that open-weight System 1 can be specialised on reviewed banking decision questions, rather than merely applying thresholds to a base model.

**Inputs.** the training split and question set; the Laya author's fine-tuning notebook

**Outputs.** a prepared dataset and reproducible notebook configuration, run metadata and a versioned checkpoint (maintainer uploads). Train only on T-106's training split; never on Portuguese test cases or the frozen T-303 suite. T-201 owns the base-versus-fine-tuned comparison and calibration on held-out data.

**Open parameters.** none: the question set is in DESIGN.md 6.1

**Done when.** a reproducible checkpoint, training provenance and evaluation-ready inference interface exist, with no frozen test data in training. T-201 independently compares it to base/calibrated Laya and simpler baselines on the same held-out set, including safety-relevant failures; the **combined thesis claim** remains incomplete until that comparison runs.

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
