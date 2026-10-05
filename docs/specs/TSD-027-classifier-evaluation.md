# TSD-027: Classifier evaluation and thresholds (T-201)

| | |
|---|---|
| Status | proposed — maintainer confirms the P-defaults at spec review |
| Branch | `eval/classifiers` |
| Task | [T-201](../tasks/T-201-classifier-evaluation.md) |
| Depends on | TSD-026 (routing on separating signals: the route and policy v3 this spec evaluates); TSD-019 (message set: calibration and test splits, test frozen first); TSD-005 (`calvino.classifiers`, calibration); TSD-015 (labels, rubric v1, L1–L5); TSD-001 (the policy that turns scores into routes) |
| Uses when it exists | TSD-020 / T-202 (the candidate checkpoint); T-203 (the Portuguese set); T-208 (the hard-rule detection) |
| Blocked by | spec approval; the T-106 splits (accepted calibration, frozen test); for the final comparison, a T-202 candidate |
| Required by | T-408 (candidate replay), T-407 (the offline flywheel turn) |
| Design | DESIGN.md 4.3, 5, 5.1, 7; ROADMAP critical path; decisions 22, 25, 30, 33, 34, 37, 42, 43, 44 |

## Purpose and boundary

Answer the thesis question honestly: **does specialising System 1 change
decisions, and is it worth it against simpler things?** Compare eight
variants (P1) on one frozen test split, fit every temperature on the
calibration split only, choose thresholds by expected cost on the
calibration split only, and write the result as a new immutable policy
version. Safety-relevant misses are reported separately from accuracy, because
accuracy can rise while a missed handoff gets worse.

**Where this stands (decision 44).** Policy v3 is the default: the route no longer reads
`needs_human` (AUROC 0.39 to 0.49 against the `needs_person` label, at chance) and routes on the
workflow area, the "talk to a person" intent and injection. Its thresholds are round numbers
fixed before a confirmation run on 110 and 84 exploratory, team-written rows `[measured]`, not
fitted numbers and not a T-106 split. This spec supplies what that evidence cannot: calibration
on a reviewed calibration split, a comparison against simpler baselines on a frozen test split,
and thresholds chosen by a stated cost, all under one pre-registered protocol.

This spec owns the variants, the metrics, the calibration procedure, the
pre-registration protocol, the cost model, the threshold choice and the report.
It does **not** own:

- **Training the candidate.** That is TSD-020. A candidate that does not beat
  calibrated base Laya is a valid result (decision 34), never a reason to retrain
  after looking at the test split (decision 42).
- **The hard rule for an explicit request for a person.** That is T-208. Here the
  rule is a fixed input (P10).
- **What `confidence` means in the route.** Policy v3 already takes it from the area
  answer alone (decision 44), which largely answers T-209. This spec checks that choice on
  the T-106 splits and does not redefine it.
- **Replay and promotion.** T-408 replays a candidate policy against logged
  decisions and T-407 records the maintainer's sign-off.
- **The Portuguese set and the full fairness suite.** T-203 and T-405.

The 50 committed T-303 cases stay frozen. They are not used to fit a
temperature, pick a threshold, write a rule or train a model. They reappear only
in T-408's replay, labelled as such.

Nothing in this spec reports a Laya figure. Every number will come from a
committed report with its sample size and evidence label.

## What the sample can and cannot show

The message set is small by design (TSD-019 P1: calibration 240, and a test split of
300 in which 60 are the adversarial and hand-written supplement). Intervals on it are wide, so the spec states them in
advance `[computed]`:

| Observed | n | 95% Wilson interval |
|---|---|---|
| 80% accuracy (240 correct) | 300 | 75.1% to 84.1% |
| 10 misses | 100 | 5.5% to 17.4% |
| 90 positives | 300 | 25.1% to 35.4% |
| 0 misses | 30 | 0% to 11.4% |

Consequences the spec builds in: a difference smaller than about 5 points on the
full test split is not detectable; **"zero missed handoffs in 30" still allows a
true miss rate of about 11%**; every slice under 30 messages is flagged, not
failed (decision 25), and no claim is made from one. The success criteria in P8
are written with these widths in mind.

## Proposed defaults (maintainer confirms at spec review)

- **P1: eight variants, one split.** All variants answer the same questions for
  the same test messages:

  | # | Variant | What it is |
  |---|---|---|
  | V0 | Majority | the most frequent class per question in the train split |
  | V1 | Rules | keyword and phrase rules (P2) |
  | V2 | Logistic regression | trained on the train split, calibrated on the calibration split (P3) |
  | V3 | Base Laya, raw | the pinned base checkpoint as it answers today |
  | V4 | Base Laya, calibrated | V3 with Calvino's temperatures (P4, P5) |
  | V5 | Candidate, raw | the T-202 candidate as it answers (extra row: what calibration buys on it) |
  | V6 | Candidate, calibrated, all five questions | the candidate answers all five questions, with Calvino's temperatures |
  | V7 | Candidate, calibrated, hybrid | `needs_human` and `workflow_area` from the candidate, `intent`, `clear_enough` and `injection` from base (decision 42) |

  V5 to V7 run only when a candidate exists; otherwise they report
  `not run: T-202` and the base rows stand as the interim result. TSD-020's
  obligation that T-201 measure the untrained heads is met by V6 against V4
  (does the candidate degrade `intent`, `clear_enough` and `injection`?) and by V7
  (what the hybrid costs and buys).
- **P2: the rules baseline is written before the test split is read, and frozen.**
  `evaluation/baselines/rules-v1.yaml` holds phrase and keyword lists for the
  two first-slice questions, a precedence order and nothing else. It is written
  by looking at the **train** split and the rubric only, reviewed by the
  maintainer, and committed before the pre-registration (P7). It may not use
  test, calibration or T-303 text. It is deterministic and has no model. Its
  purpose is the honest floor: what a person with a keyword list achieves.
- **P3: the logistic regression is the standard cheap learned alternative.**
  Multinomial logistic regression on TF-IDF features (word 1–2-grams and
  character 2–5-grams), L2 penalty, trained on the **train split only**. Its
  one hyperparameter (the penalty strength) is chosen by 5-fold cross-validation
  **inside the train split, grouped by customer hash** so one customer never
  sits on both sides of a fold. Calibration data is not used to choose it.
  `scikit-learn` is added as a dependency for this (it is not in
  `pyproject.toml` today); the alternative, a hand-written numpy
  implementation, is rejected because a second implementation of a standard
  model is a second thing to get wrong. The fitted model is rebuilt at run time
  from the train split and a fixed seed, and its coefficient hash goes into the
  report.
- **P4: temperature scaling in its exact multi-class form.** laya returns
  probabilities, not logits, but `softmax(z / T)` can be computed from them:
  `p'_i is proportional to p_i^(1/T)`, renormalised. One temperature per
  (question type, option count), as DESIGN 4.3 rule 2 says: the two-option
  binary questions share one, the five-option `workflow_area` has its own, and
  the six-option `intent` its own. It minimises the negative log likelihood of
  the labelled option on the **calibration split**, over a fixed grid that
  reaches at least 8 and is refined by a bounded one-dimensional search. The
  fitted values, their sample size and the SHA-256 of the calibration file go
  into the report. Calibration is also reported per language variant (MX, CO,
  AR), each cell with its n; cells under 30 are flagged. The existing
  binary-event `Calibrator` stays for the reliability plot and ECE.
- **P5: Calvino's temperatures are applied at runtime, or "calibrated" means
  nothing.** Today Calvino's calibration code is offline: nothing in the hub,
  the API or the policy applies a fitted temperature, so the policy sees laya's
  own probabilities (including the temperatures baked into the checkpoint's
  `rl_agent_config.json`). Thresholds chosen on calibrated numbers would then act
  on numbers the system never sees. Default: `classifiers.yaml` gains, per
  checkpoint, `temperatures` (question id to T) and `temperature_fit` (the
  calibration file's SHA-256, n and date); `LayaClient.classify` applies them to
  each answer (power transform, then `confidence` recomputed as the maximum
  probability) before the answer leaves the client. This amends TSD-005. The two
  alternatives are rejected: leaving laya's baked temperatures alone hides the
  mismatch, and rewriting a published checkpoint's config edits an artifact the
  run record names by hash. Because temperatures compose into one temperature,
  the baked laya temperature and Calvino's fit multiply; the report states both.
- **P6: the cost model is DESIGN 5's, with stated defaults.** Expected cost is the
  sum over test messages of a cost for the pair (route the policy chose, route
  the message needed). The route a message needed comes from its **rubric
  labels**, not from a model: the truth route follows `decide_route`'s own order,
  so a message is `human` if its workflow area is dispute or fraud, or it is
  flagged for injection, or `needs_person` is true; otherwise `out_of_scope` if
  its area is out of scope; otherwise `clarify` if `clear_enough` is false;
  otherwise `agents`. (Under v3 the route's own `clear_enough` gate is off, so an unclear
  message is caught only by the stuck-payment floor and the area confidence; the report
  counts the unclear messages that reach `agents`. The Gate still parks an unclear write.)
  Default costs `[hypothesis]`, in arbitrary units:

  | Chosen route | Needed route | Cost | Meaning |
  |---|---|---|---|
  | agents | human | 20 | a missed handoff |
  | human | agents | 1 | an unnecessary escalation |
  | clarify | agents | 0.3 | a question the customer did not need |
  | agents | clarify | 5 | acting on a guess |
  | human | clarify | 0.5 | |
  | clarify | human | 2 | a delay, no harm done |
  | agents | out_of_scope | 2 | |
  | human | out_of_scope | 0.3 | |
  | other pairs | | 0 if equal, 1 otherwise | |

  The cost of a missed handoff is also swept at 5, 20 and 50 and the frontier is
  reported at each, because the default is a judgment, not a measurement.
  **Do-no-harm constraint:** a chosen threshold may not increase the number of
  safety-critical misses on the calibration split (a dispute, fraud, injection or
  explicit-request message sent to `agents`) over what the same variant produces
  at the current policy v2 thresholds.
- **P7: pre-register, then read the test split once.** The order is fixed:
  1. T-106 freezes the test split first (TSD-019).
  2. Fit the temperatures and choose the thresholds on the calibration split.
  3. Commit `reports/classifiers/preregistration-<date>.json`: the variants,
     checkpoint pins, the rules file and coefficient hashes, every temperature,
     every threshold, the cost matrix and the sweep, the calibration-file hash and
     the success criteria (P8).
  4. Run the test split with `--final`. It refuses to run unless the
     pre-registration is committed, unmodified and matches the inputs it loads.
  5. Write the report. A re-read of the test split is possible but is counted and
     printed as an additional read; a changed threshold after a read is a new
     pre-registration and a stated deviation.
  This is how "thresholds are chosen without consulting the final test split"
  becomes something the code enforces.
- **P8: success criteria, fixed before the test split is read `[hypothesis]`.**
  The candidate (V6, and V7 where it matters) **beats** calibrated base Laya
  (V4) on the route only if all three hold at their pre-registered operating
  points, under the policy the pre-registration names:
  1. *Safety non-inferiority:* the candidate misses no more safety-critical
     messages than V4 (a count with its denominator and Wilson upper bound).
  2. *Benefit:* the candidate sends fewer unnecessary escalations to a person,
     and a paired bootstrap 95% interval on the per-message difference excludes
     zero.
  3. *Calibration:* its ECE on the test split is no worse than V4's by more than
     the pre-registered margin, stated in the pre-registration.
  Failing any is reported as "did not beat", which is a valid result (decision
  34). Whether "beats" justifies promotion is T-407's and T-408's judgment, not
  this spec's. The paired bootstrap uses a fixed seed and 10,000 resamples.
- **P9: the thresholds become a new immutable policy version, `v4`.** Released
  policy files are never edited. `policy/v3.yaml` exists and is the default
  (decision 44), so the next free version is `v4`; decision 33's reservation of
  `v3` for per-language thresholds was consumed by decision 44, and a per-language
  version takes the number after this one. Default: T-201 writes `v4` with the route
  thresholds fitted on the Spanish calibration split, and records the Portuguese
  evidence from T-203 as a recommendation; it applies a stricter Portuguese
  margin only once the hub reads per-language scores. **T-201 changes no Gate
  threshold:** `gate.*` limits and minimum scores guard writes and stay as they
  are.
- **P10: route-level, classifier-only, twice.** Each variant's answers are
  turned into a route by `decide_route` under policy v2, policy v3 (the default)
  and the pre-registered candidate policy. Hard-rule facts are inert, except that every
  variant is run **twice**: once with Laya alone, and once with the deployed
  explicit-request detection in front (`HR-ASKS-HUMAN`, today's phrase list or
  T-208's, the version named in the report). Evaluating Laya alone would recreate
  an overlap the running system does not have, because that rule runs first.
- **P11: Portuguese is evaluation only.** When T-203 exists, every variant is run
  on it with the Spanish temperatures and thresholds and reported as its own
  slice, never fitted or tuned (decisions 22 and 37). Until then the report says
  `not run: T-203`.

## Data and slices

- **Inputs:** `evaluation/message-set/v1/{train,calibration,test}.jsonl`
  (TSD-019), each with its acceptance record; the rubric labels on every row.
  Train is read only by V0, V1 (to author rules) and V2. Calibration is read only
  to fit temperatures and choose thresholds. Test is read once (P7).
- **Slices reported:** all of test; each language variant (MX, CO, AR); the
  the 240-message base slice against the 60-message supplement inside the test
  split (adversarial rewordings and
  hand-written rows, TSD-019 P1); reviewed against unreviewed rows (their scores
  are never pooled silently); and safety-critical classes alone (dispute or fraud,
  injection, explicit request).
- **Every cell states its n** and is flagged when under 30 (decision 25).
- **No leakage:** the same guard TSD-020 uses (text overlap, shared keys,
  acceptance) is run over the inputs of every variant, so a variant cannot be
  trained or fitted on text it is then scored on.

## Metrics

Per question and variant, with sample size and a 95% Wilson interval where a rate
is quoted: accuracy; per-class precision and recall (macro-averaged for the
five-option question); the confusion matrix; ECE and Brier before and after
temperature scaling and a reliability plot. For the route:

- **Safety-relevant misses, reported before accuracy:** missed handoffs by class
  (dispute or fraud, injection, explicit request, other `needs_person`), each with
  numerator, denominator and upper bound.
- Unnecessary escalations; clarifications asked unnecessarily; acting on a guess.
- Expected cost at the default matrix and at the 5, 20 and 50 sweep.
- **Per-signal AUROC with a 95% interval,** each signal against its own label:
  workflow area (dispute or fraud), the "talk to a person" intent, injection, and
  `needs_human` as a diagnostic. This is the measurement that showed `needs_human` at
  chance, now on reviewed splits.
- The **frontier**: for each variant, sweep v3's route thresholds (`talk_to_person_at`,
  `dispute_or_fraud_at`, `injection_at`, `min_stuck_payment`, `min_confidence`), one at a
  time from v3's values over a fixed grid, and report (share handled by agents, missed handoffs, unnecessary escalations) on
  the calibration split, with the chosen point marked. The same table is
  reported on test only at the pre-registered point.
- Paired comparisons use the bootstrap in P8, never two unpaired intervals.

## Interfaces

**`calvino.classifiers.calibration`** (extended)
- `fit_temperature_multiclass(probabilities, labels) -> float` and
  `apply_temperature(probabilities, temperature) -> list[float]`, P4's form.
  A synthetic set with a known temperature is recovered.

**`classifiers.yaml` and `LayaClient`** (amends TSD-005 and TSD-020)
- `temperatures` and `temperature_fit` per checkpoint (P5). `LayaClient` applies
  them and recomputes `confidence`; a checkpoint with none behaves as today.

**`calvino.evaluation.classifier_eval`** (new)
- Variants implement one protocol, `predict(message) -> dict[question_id,
  probabilities]`: `Majority`, `RulesBaseline`, `LogisticBaseline`,
  `LayaVariant(checkpoint, temperatures)` and `Hybrid`.
- `truth_route(labels)` (P6), `route_for(answers, policy, with_hard_rule)` (P10),
  the metrics above, `wilson`, `paired_bootstrap`.

**`scripts/run_classifier_evaluation.py`**
- `--stage fit`: reads train and calibration, fits temperatures, sweeps the
  frontier, chooses thresholds, writes a draft pre-registration. Never opens the
  test split.
- `--stage final`: refuses unless P7's conditions hold; reads test; writes
  `reports/classifiers/T-201-<date>-<git-sha>.md` and `.json`.
- Report header: message-set version and file hashes, checkpoints (name, commit,
  digest), laya version, temperatures (laya's baked and Calvino's, with n),
  policy versions, cost matrix, seeds, the hard-rule version, the read count.

**`evaluation/baselines/rules-v1.yaml`** (P2) and **`policy/<next>.yaml`** (P9),
with a DECISIONS entry.

## Tests (offline: no network, GPU, laya install or keys)

- Temperature fit recovers a known temperature on a synthetic set, and
  `apply_temperature` keeps probabilities summing to one and the arg-max stable.
- `LayaClient` with a fake router applies `classifiers.yaml` temperatures and
  recomputes `confidence`; no temperatures means unchanged output.
- `truth_route` branch by branch against the rubric order, and `route_for`
  against `decide_route` on fixed inputs.
- Metrics against hand-computed values; Wilson and bootstrap against known
  cases; the bootstrap is reproducible from its seed.
- Each baseline on a synthetic split; the logistic regression never reads
  calibration or test rows (checked by passing it a split object that raises).
- The cost matrix and the do-no-harm constraint choose the expected threshold on
  a constructed frontier.
- **The pre-registration protocol:** `--final` refuses when the file is missing,
  uncommitted, modified after commit, or when a loaded input's hash differs; it
  counts a second read.
- The report writer states `not run: T-202` and `not run: T-203` rows rather than
  omitting them.

## Implementation commit plan

1. `feat(classifiers)`: multi-class temperature fit and apply, with tests.
2. `feat(classifiers)`: runtime temperatures in `classifiers.yaml` and
   `LayaClient` (P5), with tests.
3. `feat(eval)`: the baselines (majority, rules, logistic regression) and the
   `scikit-learn` dependency.
4. `feat(eval)`: truth routes, route evaluation, metrics, Wilson and the paired
   bootstrap.
5. `feat(eval)`: the runner, the pre-registration protocol and the report.
6. `docs`: the AGENTS commands and layout, the CHANGELOG and the DECISIONS entry.

Commits 1 and 2 need no message set. After the T-106 splits and (for V5 to V7) a
T-202 candidate exist, a separate PR commits the pre-registration and the report.

## Done when

- The code above is merged with its tests; the temperatures can be applied at
  runtime; the baselines and metrics run on synthetic fixtures.
- With accepted splits: the `fit` stage's pre-registration is committed, the
  `final` stage report is committed, and it names every variant, split, model,
  policy and rubric version with sample sizes, calibration and safety-relevant
  errors, and states for the candidate whether it beat calibrated base Laya under
  P8.
- The thresholds are written as a new immutable policy version with the stated
  cost assumptions, chosen without reading the test split.
- Portuguese stays evaluation only.

**Timing.** Decision 44 puts submission hours away, so the T-106 splits, a T-202
candidate and this evaluation will be `not run` in the README at submission; this spec
governs the work after it. The evidence for v3 until then is the exploratory rows
and the frozen T-303 suite, which TSD-026 reports as exploratory.

**Stop rule (ROADMAP).** If no T-202 candidate exists by submission, the README
reports T-202 and T-201's candidate rows as `not run: <blocker>`, the base rows
(V0 to V4) still run as the interim result once the splits exist, and no
threshold change is presented as a fix for the over-escalation. A candidate that
does not beat calibrated base Laya is reported as such and is not a reason to
retrain on the test split.

## Open questions for the maintainer

1. P1: is the extra raw-candidate row (V5) worth its space, or drop it?
2. P3: `scikit-learn` as a dependency, or accept a hand-written model?
3. P5: apply Calvino's temperatures at runtime in `LayaClient` (amending TSD-005)?
4. P6: are 20, 1, 0.3 and the rest of the default costs yours, or do you set them?
5. *Resolved:* the next policy version is `v4`; `v3` exists (decision 44).
6. TSD-020's first slice trains `needs_human` and `workflow_area`, but v3 does not read
   `needs_human`. Should the first slice become `workflow_area` and the "talk to a
   person" intent (the signals v3 reads) instead? That is TSD-020's decision; it
   changes what the candidate rows V5 to V7 measure.

Recommended answers (proposed, not yet confirmed): 1 keep V5; 2 `scikit-learn` in the
dev group; 3 yes, with temperatures inert until a promotion PR sets them together with
a policy version; 4 accept the defaults as primary with the sweep.
