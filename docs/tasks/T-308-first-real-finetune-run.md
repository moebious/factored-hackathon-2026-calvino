# T-308: First real fine-tuning run: readiness and dry-run record hygiene

| | |
|---|---|
| Wave | 2 (thesis) |
| Branch | `docs/t308-finetune-readiness` (part A); part B is maintainer work, then a record PR |
| Depends on | T-202 (code merged, #116), T-106 (accepted splits), TSD-020 run plan |
| Blocked by | part B: dataset access, generation key, the maintainer's review and `acceptance.json`, Kaggle and Hugging Face settings |
| Model | standard model for part A; the maintainer for every judgment in part B |
| Can run in parallel | part A now; part B in order |
| References | [TSD-020](../specs/TSD-020-laya-fine-tuning.md), decision 42, [TSD-019](../specs/TSD-019-message-set.md), `reports/finetune/` |

**Goal.** Make the first *real* fine-tuning run executable without discovering a missing step in the middle, and make the repository say truthfully what the first Kaggle execution was.

**Why this task exists.** An audit on 2026-10-05 compared a status summary against the repository and found:

- **What exists.** The exporter, guard, notebook and run record are merged (#116, #118). The notebook on Kaggle is identical to the repo's. The pipeline ran end to end on two T4 GPUs, published `kevago/calvino-laya-ft@t202-run1` and wrote a valid run record `[measured]`. That retires the GPU-path risks recorded in the notebook PR (DDP, fp16, push, tag, digest check, record assembly), under torch 2.11.0, transformers 5.16.1 and laya 0.3.24.
- **What that run was.** Its input SHA-256 (`5f865b98…`) is the hash of the **synthetic test fixture** `tests/fixtures/message-set/v1/train.jsonl`: 8 train items and 2 hold-out items, **4 seconds** of training, 2 "reviewed" rows `[measured]`. It is a **pipeline dry run**, not a T-106 split. Its 25% training fit says the model barely trained on 8 items; it is not a failure of Rule R and not evidence about fine-tuning.
- **What the repository says instead.** The README lists the run as `done`, "executed on Kaggle", fit 25% below 90%, with no mention of the fixture. The backlog marks T-202 `done (run 1)`. `classifiers.yaml` carries an entry named `candidate` pinned to that checkpoint. A reader, or T-201's pre-registration, could take it for the real candidate.
- **What does not exist.** No `train.jsonl`, `calibration.jsonl`, `test.jsonl` or `acceptance.json`; the export refuses to run without them (by design).

## Part A: record hygiene (docs and config, can start now)

| # | Action | Owner |
|---|---|---|
| A1 | The backlog and README say T-202 is **in progress: pipeline dry run only**, not `done`; the README row names the fixture, the 8 items and the 4 seconds, and states that no Laya result exists | agent, maintainer reviews |
| A2 | `reports/finetune/README.md`: an index saying what each record is (run, data kind, status), starting with `t202-run1` = dry run on the fixture, **not a candidate** | agent |
| A3 | Rename the `classifiers.yaml` entry `candidate` to `dry-run-1` (keep the pin and `run_record` link, keep `default: base`) so nothing downstream mistakes it for the candidate | maintainer decides, agent edits |
| A4 | Record that the dry run consumed Hub tag `t202-run1`, so the first real run is `t202-run2` while the run plan's own "run 1/2/3" stay plan names. A DECISIONS entry amends the run plan wording; no tag is deleted ("never overwritten") | agent drafts, maintainer approves |
| A5 | A run record must say what its data was. The exporter marks fixture input in the manifest, and `FineTuneRunRecord` carries it, so a fixture run can never be written as an ordinary run | agent (code, its own PR) |
| A6 | Add a note to the Hub model card of `kevago/calvino-laya-ft`: "dry run on 8 synthetic fixture items, not a candidate" | **maintainer only** (needs the account) |

## Part B: readiness for the first real run

| # | Gate | Owner | How it is verified |
|---|---|---|---|
| B1 | Code on `main` | done | `ls scripts/export_finetune_dataset.py notebooks/t202_laya_finetune_kaggle.ipynb` |
| B2 | The first slice is decided: TSD-020 P3 trains `needs_human`, but policy v3/v4 does not read it. Candidates for the slice: `workflow_area` plus the "talk to a person" intent. The intent label exists only on stuck-payment rows, so what the intent head learns for other messages must be decided first | **maintainer decides**, agent amends TSD-020 and the exporter | TSD-020 P3 and the exporter agree; the export fixture covers the new items |
| B3 | T-106 inputs: dataset access (the seed-drawing credentials), the generation key, the secret salt and its backup, the drafted messages, your P4 review, and a written `acceptance.json` (accepted, at most one defect, the SHA-256 of the reviewed file) | **maintainer** | the three message files and `acceptance.json` exist; TSD-019's checks pass |
| B4 | The export passes on real data | agent runs | `uv run python scripts/export_finetune_dataset.py --out <dir>` exits 0; every guard check passes; the manifest counts are plausible |
| B5 | Kaggle: the export uploaded as a **private** dataset and attached at `/kaggle/input/calvino-t202-export`; secret `HF_TOKEN` added (fine-grained, write access to `kevago/calvino-laya-ft` only); accelerator **GPU T4 x2** (the notebook asserts exactly two GPUs, so a P100 fails by design); internet on | **maintainer** | the notebook's first cells print the export counts and "base verified" |
| B6 | The notebook on Kaggle is still identical to the repo's | agent compares | a cell-by-cell comparison through Kaggle's public pull endpoint (done once on 2026-10-05: 13 of 13) |
| B7 | `RUN_NUMBER = 2` in the constants cell (tag `t202-run1` is taken; the push cell refuses an existing tag) | maintainer | the push cell prints `t202-run2` |
| B8 | The run plan is understood: run 1 as written; judge by training-set fit only (Rule R, 90% on both questions); later runs only by the plan's rules; nothing after reading calibration or test | maintainer | decision 42 |

## Part C: after the run

- Download `run_record.json` from the Kaggle output; `write_run_record` validates it and writes `reports/finetune/`; a PR commits it.
- If Rule R passes, a separate PR names the candidate in `classifiers.yaml`. Promotion stays a later PR with T-201's report and T-407's sign-off (P7).
- T-201 pre-registers its thresholds before any test read (TSD-027).

## Boundaries

- This task does not produce the message set or run training; T-106 and the Kaggle run do. It makes the path to them explicit and the record of what already ran accurate.
- An agent cannot do A6, B3, B5, B7 or any decision: they need the maintainer's accounts, credentials or judgment. An agent never pushes or opens a PR on its own initiative.

## Timing

Submission is hours away, so part B will not complete before it. The README should read "T-202: pipeline verified, first real run `not run`: waiting on the T-106 splits" until it does (ROADMAP stop rule).

## Done when

1. A1 to A5 are merged and the README no longer calls the dry run a fine-tuning result.
2. B1 to B8 are each verified with the evidence in their row, recorded in this card's status.
3. The first real run has started with `RUN_NUMBER = 2`.

**Status.** Part A in progress; part B blocked on the maintainer.
