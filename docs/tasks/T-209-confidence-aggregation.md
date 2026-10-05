# T-209: What the route's `confidence` should mean

| | |
|---|---|
| Wave | 2 |
| Branch | `eval/route-confidence` |
| Depends on | T-106 (calibration and test splits), T-201 for the final threshold |
| Blocked by | — |
| Model | strong model or maintainer review (judgment checkpoint: it changes thresholds and the meaning of a score) |
| Can run in parallel | yes, but it shares `policy/` with T-201 and must rebase on it |
| References | `scores_from_answers` in `src/calvino/api/decide.py`; `decide_route` (TSD-001); `policy/v2.yaml`; decisions 4, 18, 30, 33; DESIGN 6.1 |

**Goal.** Decide what the route's `confidence` score is computed from. Today it is the minimum `answer_confidence` over all five Laya answers (`scores_from_answers`, used by both the demo endpoint and the hub). Its docstring calls that "the most conservative aggregate until the hub defines the real one (T-204)", and it never became a decision of its own.

**Evidence** (a one-off diagnostic on 2026-10-05, the pinned base checkpoint run on the 43 suite messages that have text; the first step re-derives it):

- `[measured]` The pinned checkpoint reproduces the committed report exactly: `needs_human` differs by 0.0 on all 43 messages.
- `[measured]` The minimum is set by the `intent` answer in 14 of 43 cases and by `workflow_area` in 13; `needs_human` sets it in 10, `clear_enough` in 5, `injection` in 1. The `intent` question only has meaning for stuck payments, yet it gates every message.
- `[measured]` In the committed run `RT-CLARIFY-CONFIDENCE` fired on 15 of 50 cases. In the 13 of those with message text, 9 were expected to be explained or acted on, not clarified. This is a separate failure from over-escalation: it lowers outcome agreement (22/50) without sending anyone to a person.
- `[measured]` Median per-question confidence is 0.706 for `workflow_area`, 0.773 for `intent`, 0.750 for `needs_human`, 0.843 for `clear_enough` and 0.887 for `injection`; the share below the 0.60 threshold is 17/43, 11/43, 8/43, 6/43 and 6/43. A five-option question gives a lower maximum probability than a two-option one for the same certainty, so the minimum compares unlike things.

**Decision to make.** Which answers feed `confidence`, and whether it stays one number. Options to weigh, none chosen here:

1. Only the answers the verdict depends on (`needs_human`, `clear_enough`), leaving `intent` to the stage that needs it.
2. `intent` counts only when `workflow_area` says stuck payment.
3. Separate thresholds per question instead of a minimum.
4. Keep the minimum and move `min_confidence`.

Each option is judged by the safety-relevant errors first (a real escalation lost, a write attempted on a guess), then by wrongly clarified cases.

**Inputs.** the T-106 calibration split for fitting and the frozen test split for the final read; per-question probabilities from `LayaClient`; the current policy files.

**Outputs.** a short decision record; a new immutable policy version with its assumptions stated; an offline comparison of the options on the same held-out set, with sample sizes, safety-relevant errors and wrongly clarified counts; T-408 replay evidence for the verdicts that change. Version numbering: decision 33 reserves `v3` for per-language thresholds, so the spec checks the next free number against T-201 first.

**Constraints.**

- The 50 T-303 cases are not used to choose the aggregate or any threshold. The numbers above only motivate the question.
- A change to what `confidence` means is a policy change, not a harness tweak: released policy files are immutable (decision 18).
- Fine-tuning's first slice trains `needs_human` and `workflow_area`, not `intent`, so this task is independent of T-202 but T-201 should compare the options on both base and fine-tuned scores.

**Done when.** the chosen definition is written down with its reason; its policy version is committed with replay evidence; the comparison table with denominators exists; no hard rule or Gate threshold has weakened (the Gate's `min_confidence` and `min_clear_enough` still guard writes).

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number), including the exact per-question table, and get the maintainer's approval before any code.
