# T-208: Hard rule for an explicit request for a person

| | |
|---|---|
| Wave | 2 |
| Branch | `feat/human-request-rule` |
| Depends on | T-106 (a held-out set of phrasings), T-001 |
| Blocked by | — |
| Model | strong model or maintainer review (judgment checkpoint: it changes who reaches a person) |
| Can run in parallel | yes |
| References | AGENTS.md ("hard rules run before Laya and always win"); DESIGN 4.2; TSD-001 (`HR-ASKS-HUMAN`); `HUMAN_REQUEST_PHRASES` in `src/calvino/hub/graph.py`; decision 4 |

**Goal.** Make `HR-ASKS-HUMAN` catch what customers actually write, and stop it firing on messages that do not ask for a person. Today the rule exists, but the detection behind it is a list of 11 phrases matched as raw substrings.

**Evidence** (a one-off diagnostic on 2026-10-05; the first step re-derives it from committed files):

- `[measured]` Of the 3 explicit requests for a person in the 50-case suite, the rule caught 2 (`AC-4`, `ORC-020`). `ORC-021` ("Necesito que un humano revise mi cuenta") was missed and reached a person only because Laya scored `needs_human` 0.97.
- `[measured]` On 14 probe sentences written for the diagnostic (synthetic, not part of any set), the phrase list missed 11 natural phrasings: "pásame con un asesor", "quiero hablar con un humano", "comunícame con un agente", "quiero que me atienda una persona", "let me talk to an agent" and others.
- `[measured]` The same list fired on 3 of 3 sentences that do not ask for a person, because matching is a plain substring test: "el **representante** legal de mi empresa…", "mi **agente humano** de seguros…", "**hablar con alguien** de mi familia…".
- `[hypothesis]` A reliable rule lets Laya stop being the only thing that separates explicit requests from routine questions. The measured overlap behind decision 30 and the ROADMAP critical path is one routine sentence (`AC-1` and `AC-8`, the same text, `needs_human` 0.8872) above one explicit request (`AC-4`, 0.8741) that this rule already catches. Whether the roadmap's "fine-tuning is the only lever" still stands is the maintainer's call, not this task's.

**Inputs.** the T-106 splits, where the rubric's "talk to a person" intent and the non-request negatives are labelled; the current detection code and its tests.

**Outputs.**

- A detection that handles accents, case, word boundaries and Spanish and English variants, with its phrase data versioned and reviewed like policy data rather than buried in code (open parameter below).
- Unit tests on both sides: a table of requests that must fire and a table of look-alike sentences that must not.
- A measurement on the T-106 held-out phrasings: recall and false-positive rate, each with its denominator. Both are reported, because a false hit sends a routine customer to the human queue, which is the failure this whole thread is about.
- The replay effect: which logged verdicts change under the new detection, using T-408's delta matrix once it exists.

**Open parameters.** where the phrase data lives (a versioned file next to `policy/` or in the hub package); whether detection changes need a new policy version or only a harness release, since `asks_for_human` is a harness fact and the policy only reads it; the matching approach (word-boundary patterns, or a stricter token match); how Portuguese is treated (evaluation only, never tuned on, decision 37).

**Constraints.**

- The 50 T-303 cases stay frozen: they are not used to choose phrases, and phrases are not revised against their outcomes.
- The rule must stay deterministic and never call a model. Laya's `needs_human` stays the softer signal behind it.
- The demo path `api/decide.py` hardcodes `asks_for_human=False`; the spec states whether the demo should detect too.

**Done when.** recall and false-positive rate on the held-out phrasings are reported with denominators; every table row in the unit tests passes; the AC scenarios in `tests/scenarios/`, including AC-4, still pass; a replay of the committed decisions shows each verdict that changes, with a stable case id.

**First step:** turn this card into a full specification in `docs/specs/` (next free TSD number) and get the maintainer's approval before implementing.
