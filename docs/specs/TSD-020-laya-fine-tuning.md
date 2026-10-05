# TSD-020: Laya fine-tuning (T-202)

| | |
|---|---|
| Status | accepted — the maintainer accepted P1–P7 and the run plan below on 2026-10-05 |
| Branch | `eval/laya-finetune` |
| Task | [T-202](../tasks/T-202-laya-fine-tuning.md) |
| Depends on | TSD-019 (message set, T-106: accepted train split; test split frozen first); TSD-015 (labels, splits, leakage rules L1–L5); TSD-005 (`calvino.classifiers`) |
| Blocked by | spec approval; a GPU for the training run (Kaggle notebook, run by the maintainer); `HF_TOKEN` with write access to one model repository |
| Required by | T-201 (held-out comparison), T-407 (offline flywheel turn), T-408 (candidate replay) |
| Design | DESIGN.md 4.0.1, 6.1; ROADMAP critical path; decisions 2, 16, 22, 34 |

## Purpose and boundary

Produce **one reproducible, pinned, fine-tuned Laya checkpoint** that
`calvino.classifiers` can load as a *candidate*, trained only on the
accepted T-106 train split. This addresses the measured failure: laya
0.3.24's `needs_human` scores for routine status questions (0.67–0.89)
overlap explicit requests for a person (0.87–0.98), causing 13 of 50
unnecessary escalations in the evaluation suite `[measured]`. No policy
threshold separates the two groups (decision 30), and temperature scaling
rescales scores without reordering them.

This spec owns the training data export, the notebook, the run record, the
published checkpoint and the code path that loads it. It does **not** own:

- **Whether the checkpoint is better.** T-201 compares base, calibrated base and
  fine-tuned plus calibrated Laya against simpler baselines on the frozen
  test split, and fits the temperatures on the calibration split.
- **Promotion.** T-407 and T-408 replay the candidate under unchanged
  policy, and the maintainer signs off or rejects it. Until then the hub and
  the demo keep the base checkpoint.
- **New thresholds.** These are written by T-201 as a new immutable policy
  version.

Nothing in this spec reports a Laya accuracy figure. The notebook's
training-set fit is labelled as training fit, never as evaluation.

## Proposed defaults (maintainer confirms at spec review)

**Acceptance (2026-10-05).** The maintainer accepted P1–P7 as written, so the
"proposed" wording records the original text and the defaults now stand, with
the [run plan](#run-plan-decided-at-acceptance) below added at acceptance.
The vendor notebook (`notebooks/laya_finetune_typed_decisions_2xT4_kaggle.ipynb`
in the `NandhaKishorM/laya` repository on GitHub, not the Hub model repository)
was read in full on 2026-10-05; see [What the vendor notebook does](#what-the-vendor-notebook-does).

- **P1: method, full fine-tuning using Laya's own RLCD loop.** Start from the
  author's Kaggle notebook (`laya_finetune_typed_decisions_2xT4_kaggle.ipynb`,
  Apache 2.0): it trains the encoder and the decision head together. The
  reward is a proper scoring rule (spherical plus RPS), optimised with a
  GRPO-style policy gradient. We adapt the data cells and keep the training
  loop. LoRA is **not** used: the vendor loop is full fine-tuning, the model
  is small enough for a T4, and an untested LoRA variant of an RL loop would
  be a second experiment. QLoRA was already rejected. LoRA becomes a fallback
  only if the full run does not fit in T4 memory, recorded as a deviation.
  Caveat `[vendor]`: the vendor's own issue #741 reports a controlled A/B
  (6,000 training samples, one seed, one A100) in which soft cross-entropy
  alone scored 80.50% against 79.08% for GRPO plus the proper-reward term, and
  concludes the GRPO term shows "no measurable gain". The notebook's loss is the
  policy-gradient term plus a full-weight soft cross-entropy term, so with
  one-hot targets the run is already mostly hard cross-entropy, and run 3 of
  the run plan removes only the policy-gradient term. Run 1 keeps the loop
  unchanged anyway, because changing the objective is a second experiment; the
  run plan below says when that second experiment happens.
- **P2: hyperparameters, the vendor defaults with no search.** Settings:
  - 4 epochs;
  - micro-batch 8, gradient accumulation 4, effective batch 64 across 2 GPUs;
  - GRPO group size 4;
  - learning rate 2.5e-5 for the encoder and 1.0e-4 for the head;
  - AdamW with weight decay 0.01, a cosine schedule down to 1e-6, gradient
    clipping at 1.0;
  - seeds as the notebook sets them (shuffle seed 42 + epoch + rank, the
    temperature hold-out seed 20260922), plus a torch seed the notebook lacks
    (see the changes list below).

  There is no dev split to search on without spending calibration or test
  data, so one fixed configuration is run and reported. Any change is a new
  run with its own record. The notebook says its 6,000 typed decisions (1,200
  cases times 5 questions) take "~4 to 6 minutes total" on 2×T4 `[vendor, read
  in the notebook, not reproduced]`. Our first slice is 1,200 items (600
  messages times 2 questions). By the notebook's own formulas, 120 of them are
  held out for laya's temperatures and the other 1,080 give **64 scheduler
  updates** in all, against **348** for the vendor's 6,000 `[computed]`. A
  short run is expected, and so is a risk of under-training; the run plan
  handles that without any search.
- **P3: first slice, two questions.** `needs_human` and `workflow_area`,
  asked exactly as `calvino.classifiers.needs_human_question()` and
  `workflow_area_question()` build them (same instructions, same criteria,
  same option order, since option order is positional in Laya). The other
  three questions (`intent`, `clear_enough`, `injection`) follow only after
  T-201 has compared this slice. The candidate replaces the whole checkpoint,
  so those three answers would come from weights never trained on them; the run
  plan makes T-201 measure that. Known limitation: the vendor notebook does not
  shuffle option order during training (issue #887), and option order is
  positional in Laya. Inference uses the same fixed order, so this is
  consistent, but it can bake in position effects; the run record notes it.
- **P4: data, the accepted train split only.** Rows come from
  `evaluation/message-set/v1/train.jsonl` (TSD-019) with
  `review_verdict` not `fail`. The split must be accepted under TSD-019's P4
  rule. Calibration, test, gold, the T-303 cases and every Portuguese row
  are excluded and checked (see Leakage guard). Hard labels become one-hot
  targets with no label smoothing. Class counts per question are recorded.
  Resampling is allowed on train only and only when the datasheet already
  documents it (TSD-019).
- **P5: base checkpoint, the multilingual checkpoint at a pinned commit.**
  Use the `multilingual` checkpoint of `convaiinnovations/laya`, pinned to
  the commit the evaluation reports were run on, with laya `0.3.24` as the
  package version. The vendor notebook downloads the whole repository root
  unpinned, which is the English checkpoint (421M parameters per the
  notebook). The multilingual subfolder has the same file layout
  (`encoder/`, `tokenizer/`, `model.safetensors`, `rl_agent_config.json`,
  seen in the Hub cache), so pointing the notebook's `model_dir` at it is
  expected to work with the unchanged loop `[hypothesis]` until the first cell
  runs; that cell checks the expected files exist before anything trains.
- **P6: hosting, one Hugging Face model repository, never overwritten.**
  The checkpoint goes to `kevago/calvino-laya-ft` (public). Its contents:
  - the weights, configuration and tokenizer;
  - a model card stating synthetic training data, the parent checkpoint, the
    Apache 2.0 licence and "not for production decisions".

  Each run is a new commit, also tagged `t202-run<N>`. Calvino pins it by
  **commit SHA plus the `model.safetensors` SHA-256**, never by branch or tag.
- **P7: promotion, a pull request.** The candidate becomes the default only
  through a PR that changes `classifiers.yaml`, citing the T-201 report and
  the maintainer's T-407 sign-off. A rejected candidate stays recorded and
  unpinned.

## Run plan (decided at acceptance)

Decided on 2026-10-05, before any run, using **training-side evidence only**.
No run is ever launched, repeated or chosen after looking at calibration or
test results.

- **Run 1:** the vendor loop unchanged, with the P2 settings.
- **Rule R `[hypothesis]`:** a run is carried into T-201 only if its
  training-set fit (`train fit, not evaluation`) is at least 90% on both
  questions. The bar was chosen before any run and is not a quality claim: it
  only says the loop learned the task it was given. Every run's fit is reported
  either way.
- **Run 2, only if run 1 fails R:** the same settings with 8 epochs, twice
  P2's. It is recorded as a deviation with this reason.
- **Run 3, only if run 2 fails R:** the run 2 settings with soft
  cross-entropy only in place of the GRPO term, for the reason in P1's caveat.
  Recorded as a deviation.
- **Stop:** if run 3 fails R, no checkpoint is carried. The README then reports
  T-202 and T-201 as `not run: no run met the training-fit rule`, and the
  over-escalation stays the named failure (ROADMAP stop rule).
- **The candidate** is the first run that passes R. Earlier runs stay recorded
  and unpinned. A candidate that then fails to beat calibrated base Laya is a
  valid result and never a reason for another run.

**What T-201 measures (obligation).** On the same frozen test split, T-201
scores the candidate in two configurations: all five questions from the
candidate, and a hybrid with `needs_human` and `workflow_area` from the
candidate and `intent`, `clear_enough` and `injection` from base. The first
shows whether the untrained heads degrade; the second needs a client that loads
two checkpoints, which T-201's own specification designs (it costs a second
model call per message). The pull request that promotes a candidate names the
configuration it promotes.

## Interfaces

**`classifiers.yaml`** (repository root, beside `providers.yaml`)
- The committed record of which Laya checkpoint each role uses:
  - `default`: the name the hub loads;
  - `checkpoints`: a mapping from name to entry. Each entry has `name`,
    `slot`, `repo`, `subfolder`, `revision`, `sha256` and `laya_version`, and a
    candidate adds `run_record`, the path of its T-202 run record. `base` is
    the first entry.
- `slot` exists because laya 0.3.24's `Router` accepts only its three
  built-in names (`english`, `multilingual`, `typed-decisions`) as `models`
  keys: a candidate loads by taking over the `multilingual` slot with its own
  repository.
- It holds no keys. Changing `default` is the promotion (P7).

**`calvino.classifiers.checkpoints`**
- `CheckpointRef` (pydantic): `name`, `slot`, `repo`, `subfolder | None`,
  `revision` (exactly 40 hex characters), `sha256` (exactly 64 hex
  characters), `laya_version`, `run_record | None`. It refuses branches, tags
  and short SHAs.
- `load_registry(path) -> ClassifierRegistry` reads and validates
  `classifiers.yaml`; `registry.get(name)` returns one entry, or the default.
- `router_kwargs(ref) -> dict` builds the `laya.Router` arguments that load
  exactly this checkpoint under the `multilingual` slot:
  - `models={"multilingual": repo[/subfolder]}`;
  - `revisions={"multilingual": revision}`;
  - `sha256_digests={"multilingual": {"model.safetensors": sha256}}`.

  laya verifies the digest on load and refuses a mismatch, so a silently
  re-pointed repository fails closed.

**`LayaClient`** (TSD-005, extended)
- `LayaClient(model="multilingual", checkpoint: CheckpointRef | None = None)`.
  With a `checkpoint`, `_load_router` passes `router_kwargs(checkpoint)`.
  Without one, behaviour is unchanged.
- Each `LayaAnswer` carries `checkpoint_id` (`name@revision`, the full
  commit), or `None` when the client has no checkpoint.
  It is used in decision records and report headers so every logged verdict
  names the weights it came from.
- The installed laya version is compared with `CheckpointRef.laya_version`
  at `preload`. A mismatch raises: the keyed `--suite all` run silently used
  laya 0.3.26 instead of the pinned 0.3.24, and this check would have
  caught it.

**`scripts/export_finetune_dataset.py`**
- `--split-file evaluation/message-set/v1/train.jsonl --out <dir>`.
- Writes `items.jsonl`, one row per (message, question):
  - `item_id`, `msg_id`, `question_id`;
  - `state` (the message text exactly as `LayaClient.classify` receives it);
  - `question` (the full question definition);
  - `target_option`.
- Also writes `manifest.json`:
  - the input file's SHA-256, set version and rubric version;
  - the question-schema SHA-256 (canonical JSON of the two question
    definitions);
  - counts per question and option, reviewed and unreviewed counts, excluded
    rows with their reasons;
  - the exporter's git SHA.
- Deterministic: the same inputs give byte-identical outputs.
- The export is not committed (a build artifact). It is uploaded as a
  private Kaggle dataset, and `manifest.json` is copied into the run record.
- Exporters must exclude rows with an unset `workflow_area` from the
  workflow-area head; they must not encode a missing area as a class.
  T-202's first slice trains `needs_human` and `workflow_area` only (P3),
  so these rows train neither head in that slice. They can train the
  clarity head only if `clear_enough` is added in a later slice.

**`notebooks/t202_laya_finetune_kaggle.ipynb`**
- An adaptation of the vendor notebook. Its header cell credits the source
  and its Apache 2.0 licence and lists every change.
- Committed with outputs cleared. It never contains a token: `HF_TOKEN`
  comes from Kaggle Secrets.

**`scripts/run_evaluation.py`** (TSD-013, extended)
- `--laya-checkpoint <name>` selects an entry from `classifiers.yaml`; the
  default is `default`.
- The report header gains `Laya checkpoint` (name, repo, revision, SHA-256).
  The existing `Laya` row keeps the package version.

**`calvino.classifiers.finetune_record`**
- `FineTuneRunRecord` (pydantic) and `write_run_record(record, out_dir)`.
  These write `reports/finetune/T-202-<date>-<revision12>.json` and `.md`
  (fields below), with an evidence label on every number.

## What the vendor notebook does

Read on 2026-10-05 from `NandhaKishorM/laya`, file
`notebooks/laya_finetune_typed_decisions_2xT4_kaggle.ipynb` (41,289 bytes, last
changed upstream 2026-10-01, upstream commit `6ea584941d`; the downloaded copy
had SHA-256 `d97004a95c878e4d2d8158d0f91efa7922cdc854d7454d7a0ccda115444eccb0`).
The Apple Silicon script beside it holds the same loop; the Intel Mac here has
no MPS, so it is not used.

- **Data:** cell 6 builds one training item per (message, question) from the
  `LocalLLaMA/typed-decisions` dataset. Each item holds the tokenised sequence
  (message plus the question's instructions and criteria), the option marker
  positions and a target distribution over the options in criteria order. With
  our one-hot labels the target is `1.0` on the labelled option and `0.0`
  elsewhere.
- **Loop (cell 8, `train_ddp.py`):** DDP on two GPUs, mixed precision, gradient
  checkpointing, `max_len` 1024, head length 256. Exploration noise starts at
  0.4 and falls to 0.1; the reward weights are 0.75 (spherical) and 1.0 (RPS).
  The loss is the policy-gradient term plus 1.0 times soft cross-entropy.
- **After training:** the loop fits laya's own temperatures per question type on
  the held-out slice, writes fp16 weights, and writes `fine_tuned: true`,
  `model_name: laya-typed-decisions` and the fitted temperatures into
  `rl_agent_config.json`, which laya applies at inference. Calvino's
  temperatures are fitted separately by T-201 on top of these outputs.

**Changes the adaptation commit makes** (each recorded as a deviation in the run
record where it changes behaviour):

1. Pin `laya==0.3.24` (the notebook installs `laya>=0.1.6` and
   `transformers>=4.48.0`) and record the `torch` and `transformers` versions.
2. Download the base at the pinned commit with `allow_patterns` for the
   multilingual subfolder only (the notebook fetches the whole repository,
   unpinned) and verify the `model.safetensors` SHA-256 before training.
3. Read items from the exporter's output instead of the benchmark dataset.
4. Count dropped items and **fail** when any is dropped: the notebook silently
   discards an item whose marker count differs from its option count.
5. Seed torch: the notebook never calls `torch.manual_seed`, so the exploration
   noise is unseeded and two runs with the same settings differ. GPU
   nondeterminism remains, so reproducible means same settings, not bit-identical.
6. Hold the temperature slice out by message, not by item: with two questions
   per message, the notebook's random item hold-out can put one question of a
   message in training and the other in the hold-out. This affects only laya's
   baked temperatures `[hypothesis: small]`.
7. Delete the benchmark and evaluation cells (12–14, 17–18). They score a
   different dataset and compare against a vendor system.
8. Replace the push cell: the token comes from Kaggle Secrets, the push becomes a
   new commit tagged `t202-run<N>`, and the cell prints the commit and the
   `model.safetensors` SHA-256.
9. Extend the run record's configuration with the loop settings the notebook
   fixes in code (noise schedule, reward weights, sequence lengths, hold-out
   size and seed), so they are recorded rather than assumed.

## Kaggle notebook setup

1. **Notebook options:** accelerator *GPU T4 ×2*, internet *on*,
   persistence off.
2. **Attach the private dataset** holding `items.jsonl` and
   `manifest.json`. The first cell recomputes the SHA-256 of `items.jsonl`
   and asserts it equals the manifest.
3. **Add the `HF_TOKEN` secret:** a fine-grained token with write access to
   `kevago/calvino-laya-ft` only.
4. **Install pinned versions:** `laya==0.3.24`, plus the `transformers`,
   `torch` and `safetensors` versions recorded in the cell output.
5. **Download the base checkpoint** at P5's commit and assert the
   `model.safetensors` SHA-256 before training. Record the parameter count:
   the vendor notebook says 421M parameters while DECISIONS cites 322M, so
   the run measures it rather than repeating either figure.
6. **Train** with `torchrun --nproc_per_node=2` and the P2 settings. The
   vendor loop holds out the smaller of 400 items and 10% of the training
   items to fit its own temperatures. That is kept so the exported config is internally
   consistent, but those temperatures are **not** Calvino's calibration:
   T-201 fits Calvino's temperatures on the calibration split, on top of the
   checkpoint's outputs.
7. **Report the training-set fit only,** labelled "train fit, not
   evaluation". The vendor's benchmark-evaluation cells are deleted: they
   score a different dataset, and our held-out evaluation is T-201's.
8. **Export and push** to the repository, which becomes a new commit; tag it
   `t202-run<N>`; print the commit SHA and the `model.safetensors` SHA-256.
9. **Write `run_record.json`** to the Kaggle output for the maintainer to
   download.

## Run record

`reports/finetune/T-202-<date>-<revision12>.json` and `.md`, committed by
the maintainer's PR after the run:

- **Base:** repository, subfolder, commit, SHA-256, measured parameter count.
- **Output:** repository, commit, tag, `model.safetensors` SHA-256.
- **Environment:** laya, torch, transformers and CUDA versions; GPU model and
  count.
- **Configuration:** every P2 setting, the seed and any deviation from this
  spec, with its reason.
- **Data:** the export manifest in full (input hash, question-schema hash,
  counts, exclusions).
- **Training:** loss per epoch, wall time, and the training-set fit per
  question, labelled `train fit, not evaluation`.
- **Leakage-guard result:** the checks run, each with a pass result.

## Leakage guard

`export_finetune_dataset.py` refuses to write anything, with a non-zero
exit and the offending ids, when any of the following holds:

- **Wrong split.** A row's `split` is not `train`, or the split's TSD-019
  acceptance record is missing.
- **Text overlap.** A row's normalised message (TSD-019 normalisation)
  matches any message in:
  - the calibration or test splits;
  - the gold sheet;
  - `evaluation/cases/`;
  - any Portuguese set.
- **Shared keys.** A `seed_key` or customer hash also appears in
  calibration, test or gold (L1, L4, L5).
- **Portuguese row.** A row's `language_variant` is Portuguese: Portuguese
  is evaluation only (decision 37).
- **Unknown label.** A label does not map to an option of the question as
  built today.

Label mapping:
- `needs_person=yes` → `human needed`, and `no` → `can handle automatically`.
- `workflow_area` labels equal the option keys (the TSD-015 enum).

## Tests (offline: no network, GPU or laya install)

- **CheckpointRef validation:** accepts a 40-hex revision and a 64-hex
  SHA-256; refuses `main`, a tag, a short SHA and an uppercase or
  wrong-length digest.
- **`router_kwargs`:** produces exactly the `models`, `revisions` and
  `sha256_digests` shapes laya 0.3.24 reads, checked against a recorded copy
  of the Router signature.
- **`LayaClient` with a fake router:** the checkpoint kwargs reach the
  constructor; `checkpoint_id` appears in its output; a laya version
  mismatch raises at `preload`; no checkpoint keeps today's behaviour.
- **`classifiers.yaml`:**
  - the committed file validates;
  - `default` names an existing entry;
  - every candidate's `run_record` path exists, once one does.
- **Exporter on a synthetic fixture** (`tests/fixtures/message-set/`,
  labelled synthetic):
  - the expected items and target options;
  - a byte-identical manifest on a second run;
  - one failing fixture per leakage rule: a calibration row, gold text
    overlap, an evaluation-case overlap, a shared seed key, a Portuguese row
    and an unknown label.
- **Question schema:** the exporter's question-schema hash equals the hash of
  `needs_human_question()` and `workflow_area_question()`. A change to
  either builder fails the test until the export is regenerated, because a
  checkpoint trained on different wording is a different experiment.
- **Notebook lint:**
  - no stored outputs;
  - pins `laya==0.3.24`;
  - contains no token-shaped string;
  - reads `HF_TOKEN` only from Kaggle Secrets;
  - contains no vendor benchmark-evaluation cell.
- **Run record:**
  - a fixture record validates;
  - the `.md` writer puts `train fit, not evaluation` beside every training
    metric and names both checkpoints.
- **Evaluation runner with a fake client:** `--laya-checkpoint` selects the
  entry, and the report header shows its name, revision and SHA-256.

## Implementation commit plan

1. `feat(classifiers)`: `CheckpointRef`, `classifiers.yaml` with the base
   entry pinned, `router_kwargs`, `LayaClient` pinning, the version check,
   and tests.
2. `feat(eval)`: `--laya-checkpoint` and the report-header field, with tests.
3. `feat(data)`: the exporter, the leakage guard, the synthetic fixture and
   tests.
4. `feat(classifiers)`: the adapted notebook, the notebook lint test and the
   licence notice.
5. `feat(classifiers)`: `FineTuneRunRecord` and the report writer, with tests.
6. `docs`: the AGENTS layout (`notebooks/`, `classifiers.yaml`,
   `reports/finetune/`), README run commands and the CHANGELOG.

Commits 1, 2 and 5 do not need TSD-019 and can merge first. Pinning the
base checkpoint is worth having on its own: today the base is loaded
unpinned. After the maintainer's Kaggle run, a separate PR adds the run
record and the candidate entry in `classifiers.yaml`.

## Done when

- The code above is merged with its tests, and the base checkpoint is pinned
  by commit and SHA-256.
- The maintainer has run the notebook once on the accepted train split. The
  run record is committed, the leakage guard passed, and the checkpoint is
  on the Hub at a recorded commit and SHA-256.
- `classifiers.yaml` lists the candidate.
  `run_evaluation.py --suite tier0 --laya-checkpoint <candidate>` completes
  and its header names the candidate. Its numbers are not claimed here;
  T-201 owns the comparison.
- The README lists T-202 as done and T-201 as the open comparison.

**Stop rule (ROADMAP).** If no run happens before submission, the README
reports T-202 and T-201 as `not run: <blocker>`, and the over-escalation
stays the named failure. A checkpoint that does not beat calibrated base
Laya in T-201 is a valid reported result (decision 34), not a reason to
retrain on the test split or to adjust anything after seeing it.
