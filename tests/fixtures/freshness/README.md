# Synthetic freshness fixture

Every record in this fixture is invented for T-105. It contains no real
customer, account, transaction, or case ids. It uses MX/CO/AR country variants
and MXN/COP/ARS/USD currencies, never BRL.

`initial.jsonl` is the accepted baseline. `updates.jsonl` contains corrections,
late first-seen partitions, a deliberately late revision of a quarantined
record, and a frozen-suite sentinel. `reversion.jsonl` contains a correction
whose content returns to the original source value. Arrival dates are fixed
fixture inputs.
Generated snapshots and reports belong in test temporary directories, never
beside these committed inputs.

The `SYN-FRESH-*` customer ids are selected to exercise T-103's actual bucket
assignment: suffixes 0000, 0003, 0006, and 0007 are train; 0001 is calibration;
0002 is test.
