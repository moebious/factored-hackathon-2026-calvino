# Bank fixture (synthetic)

`synthetic_bank.json` is **synthetic test data**, invented for Calvino's tests. It holds no real customers, accounts or payments, and none of it comes from the dataset.

It covers one case each of: a normal approved entry; an approved entry whose `response_code` is null (status must stay Approved); a pending transfer (cancellable); a declined transfer (retryable); an approved transfer (cancel refused); a pending card purchase (type refused); a reversed payment; a fraud-flagged pending and declined transfer; and an open investigation. Countries are MX, CO, AR and US; currencies MXN, COP, ARS and USD.

The ids are stable: the adapter conformance suite (`tests/calvino/tools/test_conformance.py`) refers to them, so any adapter under test must be able to serve the same scenarios.
