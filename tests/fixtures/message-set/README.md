# Synthetic message-set fixtures

Made-up rows for the offline tests of the fine-tuning export (TSD-020). Every message, key,
customer hash and date here is invented. **`v1/acceptance.json` is not a real acceptance:** it
only lets the tests exercise the accepted path, and its hash is of the fixture `train.jsonl`.
The real `evaluation/message-set/v1/acceptance.json` is written by the maintainer alone after
the TSD-019 P4 review.
