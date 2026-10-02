# T-202: Laya fine-tuning on Kaggle

| | |
|---|---|
| Wave | Tier 1 (deferred by decision 17) |
| Branch | `eval/laya-finetune` |
| Depends on | T-106 |
| Blocked by | GPU (maintainer runs the notebook) |
| Model | standard model |
| Can run in parallel | yes |
| References | DESIGN.md 4.0.1 |

**Goal.** Specialise Laya on the domain's decisions.

**Inputs.** the training split and question set; the Laya author's fine-tuning notebook

**Outputs.** a prepared dataset and notebook configuration; a versioned checkpoint on the Hugging Face Hub (maintainer uploads)

**Open parameters.** [workflow] question set

**Done when.** the checkpoint is evaluated by T-201 on the same held-out split

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), with interfaces, tests and done criteria, and get the maintainer's approval before implementing.
