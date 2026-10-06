# Fine-tuning run records

One record per run of `notebooks/t202_laya_finetune_kaggle.ipynb` (TSD-020), written by
`calvino.classifiers.finetune_record.write_run_record`. A record is never overwritten.
Training numbers in a record are `train fit, not evaluation`; no record reports accuracy.

| Hub tag | Record | What it was | Status |
|---|---|---|---|
| `t202-run1` | [T-202-2026-10-05-464ee356fe2f](T-202-2026-10-05-464ee356fe2f.md) | A **pipeline dry run on the synthetic test fixture** (`tests/fixtures/message-set/v1/train.jsonl`, input SHA-256 `5f865b98…`): 8 train items, 2 hold-out items, 4 seconds. It proved the Kaggle path works end to end on 2 x T4. | **Not a candidate and not a result.** Its 25% training fit reflects 8 items, not a failed Rule R. The tag is burned, so the first real run is `t202-run2` ([T-308](../../docs/tasks/T-308-first-real-finetune-run.md)). |

A real run's record names an accepted T-106 split and an `acceptance.json` entry, and
its data section shows the reviewed and unreviewed counts of that split.
