# TSD-005: Laya service and calibration

| | |
|---|---|
| Status | draft |
| Branch | `feat/laya-service` |
| Depends on | TSD-000 |
| Required by | the policy engine's scores, the verifier's Laya checks, classifier evaluation (Wave 2) |
| Requirements | PRD FR-3, NFR-1, NFR-4 |
| Design | DESIGN.md 4.0.1, 4.3 (Laya usage rules), 7 |

## Purpose

System 1's client and the calibration tooling that makes its probabilities trustworthy.

## Interfaces

**`LayaClient`** (in `calvino.classifiers.laya`), wrapping the `laya` package's `Router`:

- pins `model="multilingual"` for customer text and preloads on start;
- batches all questions about one state into a single call;
- returns typed answers: for each question, the chosen option, the probability per option and the confidence;
- never exposes `action.act_probability`.

**Question builders** enforcing the usage rules: at most 10 options per choice; binary questions asked as two-option choices with neutral keys; no score questions for decisions that matter.

**`FakeLaya`:** deterministic, for tests. Tests that need the real model are marked and skipped in CI.

**Calibration** (in `calvino.classifiers.calibration`):

- temperature scaling fitted per (question type, option count) on a calibration split only;
- metrics: ECE and Brier score; a reliability plot written to a file;
- a script that runs fitting and evaluation on a labelled CSV.

## Behaviour and data

- A small synthetic labelled set in Spanish and Portuguese, clearly labelled synthetic, exercises the pipeline until the real labels exist.
- CPU latency per call is measured on a local run and reported as `[measured]`.

## Workflow context (decisions 16 and 17)

- The question builders implement the question set in DESIGN.md 6.1: workflow area; intent within a stuck payment; clear enough to act on; needs a person; injection.
- Classifier text is team-generated (decision 16): the synthetic labelled set here only exercises the pipeline; the dataset transcripts are never used. The real labelled set comes from T-106.
- Fine-tuning is Tier 1; this spec covers the client and calibration only.

## Tests and acceptance

- Question builders reject rule violations.
- Calibration improves ECE on a synthetic set with known miscalibration.
- The client never returns `act_probability`.

**Done when** calibration runs end to end on the synthetic set, and the unit tests pass without downloading the model.
