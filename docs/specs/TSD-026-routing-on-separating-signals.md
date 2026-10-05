# TSD-026: Routing on the signals that separate (policy v3)

| | |
|---|---|
| Status | implemented, measured and adopted as the default policy (decision 44) |
| Branch | `feat/needs-person-question` |
| Depends on | TSD-001 (`decide_route`), TSD-005 (`calvino.classifiers`), TSD-013 (evaluation) |
| Required by | TSD-020 (what the fine-tune is asked to fix), T-201, T-408 |
| Design | DESIGN.md 4.3, 6.1; decisions 22, 30, 33, 34 |

## Question

Live laya sent 2 of 50 evaluation cases to the agent (27 to a person, 19 to clarify) `[measured]`.
Was the cause the wording of the `needs_human` question, and would rewording it fix the route?

## Findings (all on live laya, in process; the exploratory rows are team-written, not a T-106 split)

1. **No, rewording does not fix it** `[measured]`. On 110 development rows (46 labelled
   `needs_person`) the "human needed" score has AUROC 0.43 with the original wording and 0.49 with
   a reworded one that uses the gold rubric's own definition (95% intervals include 0.5). It
   lowered routine scores (median 0.73 to 0.63) and left needs-a-person rows at 0.68. The
   one-off comparison script was not kept; the committed reports use the current wording.
2. **`needs_human` is one of four gates that stop routine requests** `[measured]`. Under v2 no
   routine development row reached the agent (0/64): `needs_human` stopped 32, the confidence
   aggregate (the minimum over all five answers, dragged down by the six-option intent question)
   16, `clear_enough` 7 (P(clear) is 0.04 to 0.2 for plain status messages that name no payment
   reference) and dispute/fraud false positives 7.
3. **Other signals do separate the classes** `[measured]`. AUROC against the label: workflow area
   (dispute or fraud) 0.72, intent "talk to a person" 0.75, injection 0.75, and the max of the
   three 0.86 on development; 0.72, 0.79, 0.78 and 0.80 on unseen rows, where `needs_human`
   scores 0.39.
4. **The rubric and the message-set derivation disagree on injection** (rubric example:
   `needs_person = no`; TSD-019: `true`). Injection rows score 0.1 on `needs_human` anyway, so
   this label is not what the route relies on; it is noted for the maintainer to settle.

## Policy v3 (`policy/v3.yaml`, the default)

Switches that default off in v1 and v2, so released files replay unchanged and v2 stays the default:

- `use_needs_human: false`: the score is neither required nor read (no escalate, no clarify band).
- `talk_to_person_at: 0.5`: a new gate on the intent option, `RT-TALK-TO-PERSON`.
- `min_stuck_payment: 0.5`: area "stuck payment" below it goes to clarify (`RT-CLARIFY-NOT-STUCK`).
- `min_clear_enough: null`: the route's `clear_enough` gate is off; the Gate keeps its own (0.70).
- `confidence_source: workflow_area`: confidence is the area answer's, not the minimum of all five.

The new thresholds are round values fixed before the confirmation run, not fitted numbers.

## Results

On 84 unseen rows (36 needs a person) under the frozen v3 `[measured]`, v2 against v3:

| | v2 | v3 |
|---|---|---|
| routine rows reaching the agent | 3/48 (6%) | 25/48 (52%) |
| needs-a-person rows reaching the agent | 0/36 | 7/36 (19%) |
| needs-a-person rows sent to a person | 23/36 | 17/36 |

The seven that reach the agent: four disputes phrased as "duplicate charge" or "I do not recognise
the payment" (the area question files them as stuck payments), two polite requests for a person, and
one rephrased injection. The other 29 were sent to a person or to clarify.

On the 50 frozen evaluation cases, same laya version (0.3.27), offline, template agent, reported
once and never tuned on `[measured]`:

| | v2 | v3 |
|---|---|---|
| outcome agreement | 22/50 | 26/50 |
| containment | 23/50 | 32/50 |
| escalated (15 required) | 27 | 18 |
| unnecessary / missed escalations | 13 / 1 | 5 / 2 |
| unsafe outcomes | 0/50 | 0/50 |
| `explain` cases answered correctly | 0/10 | 3/10 |

## What this does and does not show

- It is a real but partial improvement. Seven of ten explain cases still end as clarify.
- v3 moves risk from the classifier to the verifier and the Gate: 19% of needs-a-person rows now
  reach the agent. The agent still cannot write without the Gate, and a reply is verified (decision
  40), but a dispute answered as if it were a status question is a wrong answer, not an unsafe write.
- The residual errors are what a fine-tune of `workflow_area` (the first slice in TSD-020) targets:
  disputes the area question misreads, and polite requests for a person.
- The development and confirmation rows are mine and small (110 and 84), written from the rubric
  before the scores were seen; they are exploratory evidence, not a T-106 split. Rows are not
  independent customers, and the thresholds are untuned on the 50 frozen cases.

## Open questions for the maintainer

1. Adopt v3 as the default policy, or keep v2 and run v3 only in the evaluation until the
   fine-tune lands? (Default stays v2 until you decide.)
2. Is a 19% pass-through of needs-a-person rows to the agent acceptable, given the verifier and
   Gate? A dispute-vocabulary hard rule or an extra intent gate would reduce it, at the price of
   text rules in front of Laya.
3. Settle the injection label (finding 4).

## Reproduce

    uv pip install laya
    uv run python scripts/measure_routing.py --labels evaluation/exploratory/needs-person-holdout-v1.jsonl
    uv run python scripts/run_evaluation.py --suite tier0 --repeats 3 --policy v3
