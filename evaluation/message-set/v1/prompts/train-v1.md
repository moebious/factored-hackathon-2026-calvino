# Train prompt v1 — plain customer requests (TSD-019, T-106)

Version: `train-v1`. Used for the train split (and the plain drafting of
calibration) only. Produces ordinary, varied customer requests from a
generation brief: intent, country variant, seed facts and persona voice.
Never adversarial styling: no prompt-injection wordplay, no roleplay
overrides, no garbled or emoji-only text, no hostile tone. Adversarial
styling is confined to the test prompt (decision 16).

The train/calibration injection positives are ordinary-looking requests
that carry injection content in plain phrasing (per rubric v1), so the
classifiers see the positive class outside adversarial phrasing.

## Input

Each call supplies one brief:

- `intent`: what the customer wants (status, cancel, retry, open a case,
  case status, talk to a person, dispute, fraud report, out of scope).
- `country_variant`: MX, CO or AR. Write Rioplatense-free neutral
  Spanish with the variant's everyday words for money and banking
  (MX: transferencia, atorada; CO: giro, consignación; AR: transferencia,
  alias). Never Portuguese, never Brazilian references, never BRL.
- `seed_facts`: status, amount band, currency, channel and, for
  complaints, status and SLA state. Mention facts a customer would
  plausibly know (amount, rough date, channel); never invent account
  numbers, case numbers or names.
- `persona_voice`: terse or detailed, calm or worried. Vary the length
  and the opening across calls: questions, statements, requests.

## Rules

1. One request per message: the text carries exactly the brief's intent
   and pins the seed's record where the seed has one.
2. Plain phrasing always. A worried customer still writes like a person,
   not like a test case.
3. Injection positives keep the ordinary surface: the request reads like
   any other request and carries the injected instruction inside it,
   without styling tricks (no SYSTEM tags, no "ignore your rules"
   wording — that styling belongs to test).
4. Dispute and fraud-report heads describe the charge or the access
   problem concretely (merchant, date, amount) without accusing a named
   person.
5. Out-of-scope heads ask about something outside the bank's business
   (another company, homework, general knowledge) in the same plain
   voice.
6. Output only the message text, nothing else: no quotes, no preamble,
   no explanation.
