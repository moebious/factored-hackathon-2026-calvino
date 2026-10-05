"""Tests for the P2 seed-pull sampler (TSD-019, T-106).

Synthetic fixtures only: no network, GPU, keys, dataset or salt. The fake
lakehouse stands in for the live tables; customer ids are picked by hash
bucket so split placement is deterministic and offline.
"""

from __future__ import annotations

from datetime import date

import pytest

from calvino.data import seed_pull as sp
from calvino.data.splits import TRAIN_BUCKETS, customer_bucket

GATE = {"MXN": 8500.0, "COP": 2000000.0, "ARS": 175000.0, "USD": 500.0}
HARD = {"MXN": 85000.0, "COP": 20000000.0, "ARS": 1750000.0, "USD": 5000.0}

SPLIT_OF = {"train": TRAIN_BUCKETS, "calibration": range(70, 85), "test": range(85, 100)}
DAY_OF = {
    "train": date(2024, 3, 10),
    "calibration": date(2025, 8, 10),
    "test": date(2026, 2, 10),
}
COUNTRY_OF = {"MX": "México", "CO": "Colombia", "AR": "Argentina"}
PROBLEM_STATUSES = ("Declined", "Pending", "Reversed")


def bucket_ids(split: str, count: int, tag: str) -> list[str]:
    """Deterministic customer ids hashing into one split's buckets."""
    found = []
    candidate = 0
    while len(found) < count:
        text = f"synth-{tag}-{split}-{candidate}"
        if customer_bucket(text) in SPLIT_OF[split]:
            found.append(text)
        candidate += 1
    return found


class FakeLakehouse:
    """Lakehouse-shaped rows behind the interface: never the live tables."""

    def __init__(self, customers, transactions, complaints=()):
        self._customers = customers
        self._transactions = transactions
        self._complaints = complaints

    def iter_customers(self):
        return iter(self._customers)

    def iter_transactions(self):
        return iter(self._transactions)

    def iter_complaints(self):
        return iter(self._complaints)


def customer_rows(ids_variants: list[tuple[str, str]]) -> list[dict]:
    return [{"customer_id": cid, "country": COUNTRY_OF[variant]} for cid, variant in ids_variants]


def txn_row(
    record_id,
    customer_id,
    day,
    status="Pending",
    amount=4000.0,
    currency="MXN",
    txn_type="Transfer",
    channel="App",
):
    return {
        "transaction_id": record_id,
        "customer_id": customer_id,
        "transaction_date": day,
        "transaction_status": status,
        "transaction_type": txn_type,
        "amount": amount,
        "currency": currency,
        "is_fraud": False,
        "channel": channel,
    }


def complaint_row(record_id, customer_id, day, status="Open"):
    return {
        "complaint_id": record_id,
        "customer_id": customer_id,
        "creation_date": day,
        "category": "Transactions",
        "status": status,
        "sla_breached": False,
    }


def rich_split_fixture(split: str, tag: str, per_variant: dict[str, int]):
    """Customers plus one transaction or complaint row per quota unit.

    Problem rows cycle Transfer/Payment (stuck-grounding) and the three
    problem statuses; clean rows are Approved. One row per customer, so
    the customer-dedup rule never fires here.
    """
    customers = []
    transactions = []
    complaints = []
    for variant in ("MX", "CO", "AR"):
        counts = per_variant
        need = (
            counts.get("problem_transaction", 0)
            + counts.get("clean_transaction", 0)
            + counts.get("complaint", 0)
        )
        ids = bucket_ids(split, need, f"{tag}-{variant}")
        cursor = 0
        for i in range(counts.get("problem_transaction", 0)):
            cid = ids[cursor]
            cursor += 1
            customers.append((cid, variant))
            transactions.append(
                txn_row(
                    f"r-{split}-{variant}-p-{i}",
                    cid,
                    DAY_OF[split],
                    status=PROBLEM_STATUSES[i % 3],
                    txn_type="Transfer" if i % 2 == 0 else "Payment",
                )
            )
        for i in range(counts.get("clean_transaction", 0)):
            cid = ids[cursor]
            cursor += 1
            customers.append((cid, variant))
            transactions.append(
                txn_row(
                    f"r-{split}-{variant}-c-{i}",
                    cid,
                    DAY_OF[split],
                    status="Approved",
                    txn_type="Deposit",
                )
            )
        for i in range(counts.get("complaint", 0)):
            cid = ids[cursor]
            cursor += 1
            customers.append((cid, variant))
            complaints.append(complaint_row(f"k-{split}-{variant}-{i}", cid, DAY_OF[split]))
    return customers, transactions, complaints


def quotas_for(per_variant: dict[str, int]) -> dict[str, dict[str, int]]:
    return {
        "train": dict(per_variant),
        "calibration": dict(per_variant),
        "test": dict(per_variant),
    }


def test_filter_first_usable_only_when_bucket_and_date_agree():
    """A bucket/date mismatch is excluded under its bucket split, never drawn."""
    train_ids = bucket_ids("train", 2, "agree")
    customers = customer_rows([(train_ids[0], "MX"), (train_ids[1], "MX")])
    transactions = [
        txn_row("r-ok", train_ids[0], DAY_OF["train"]),
        txn_row("r-mismatch", train_ids[1], DAY_OF["calibration"]),
    ]
    candidates, skipped = sp.candidates_from_lakehouse(FakeLakehouse(customers, transactions))
    assert skipped == {}
    drawn, report = sp.pull_seeds(
        candidates,
        quotas={"train": {"problem_transaction": 1}, "calibration": {}, "test": {}},
        floors={"train": 0, "calibration": 0, "test": 0},
        gate=GATE,
        hard=HARD,
    )
    assert [d.candidate.record_id for d in drawn["train"]] == ["r-ok"]
    assert drawn["calibration"] == []
    assert report.excluded.get("train") == 1
    assert report.considered.get("train") == 2


def test_p6_margins_excluded_before_sampling():
    """Amounts near the gate line or past the hard line never reach the draw."""
    train_ids = bucket_ids("train", 3, "margin")
    customers = customer_rows([(cid, "MX") for cid in train_ids])
    transactions = [
        txn_row("r-clear", train_ids[0], DAY_OF["train"], amount=4000.0),
        txn_row("r-near-gate", train_ids[1], DAY_OF["train"], amount=8000.0),
        txn_row("r-over-hard", train_ids[2], DAY_OF["train"], amount=90000.0),
    ]
    candidates, _ = sp.candidates_from_lakehouse(FakeLakehouse(customers, transactions))
    drawn, report = sp.pull_seeds(
        candidates,
        quotas={"train": {"problem_transaction": 1}, "calibration": {}, "test": {}},
        floors={"train": 0, "calibration": 0, "test": 0},
        gate=GATE,
        hard=HARD,
    )
    assert [d.candidate.record_id for d in drawn["train"]] == ["r-clear"]
    assert report.excluded.get("train") == 2


def test_stratified_quotas_met_per_kind_and_variant():
    """A rich pool draws every (kind, variant) cell exactly to quota."""
    per_variant = {"problem_transaction": 6, "complaint": 3, "clean_transaction": 3}
    tables = [rich_split_fixture(split, "strat", per_variant) for split in ("train", "test")]
    customers = customer_rows([row for table in tables for row in table[0]])
    transactions = [row for table in tables for row in table[1]]
    complaints = [row for table in tables for row in table[2]]
    candidates, skipped = sp.candidates_from_lakehouse(
        FakeLakehouse(customers, transactions, complaints)
    )
    assert skipped == {}
    drawn, report = sp.pull_seeds(
        candidates,
        quotas={
            "train": {kind: count * 3 for kind, count in per_variant.items()},
            "calibration": {},
            "test": {kind: count * 3 for kind, count in per_variant.items()},
        },
        floors={"train": 0, "calibration": 0, "test": 0},
        gate=GATE,
        hard=HARD,
    )
    for split in ("train", "test"):
        assert report.drawn[split] == 36
        kinds = dict(report.drawn_kinds[split])
        assert kinds.get("complaint") == 9
        assert sum(kinds.values()) == 36  # re-role only renames transaction kinds
        variants = dict(report.drawn_variants[split])
        assert variants == {"MX": 12, "CO": 12, "AR": 12}


def test_quota_shortfall_fails_closed():
    """A short quota cell raises instead of drawing short or backfilling."""
    customers, transactions, complaints = rich_split_fixture(
        "calibration", "thin", {"problem_transaction": 3, "complaint": 3}
    )
    candidates, _ = sp.candidates_from_lakehouse(
        FakeLakehouse(customer_rows(customers), transactions, complaints)
    )
    with pytest.raises(sp.SeedShortfall, match="calibration/complaint"):
        sp.pull_seeds(
            candidates,
            quotas={
                "train": {},
                "calibration": {"problem_transaction": 3, "complaint": 24},
                "test": {},
            },
            floors={"train": 0, "calibration": 0, "test": 0},
            gate=GATE,
            hard=HARD,
        )


def test_complaint_floor_enforced_on_drawn_counts():
    """A draw meeting its quotas but missing the floor still fails closed."""
    customers, transactions, complaints = rich_split_fixture(
        "train", "floor", {"problem_transaction": 6, "clean_transaction": 3}
    )
    candidates, _ = sp.candidates_from_lakehouse(
        FakeLakehouse(customer_rows(customers), transactions, complaints)
    )
    with pytest.raises(sp.SeedShortfall, match="below floor"):
        sp.pull_seeds(
            candidates,
            quotas={
                "train": {"problem_transaction": 6, "clean_transaction": 3},
                "calibration": {},
                "test": {},
            },
            gate=GATE,
            hard=HARD,
        )


def test_non_stuck_problem_types_excluded_before_sampling():
    """Problem transactions outside Transfer/Payment never reach the draw."""
    ids = {}
    for variant in ("MX", "CO", "AR"):
        ids[variant] = bucket_ids("train", 2 if variant == "MX" else 1, f"stucktype-{variant}")
    customers = customer_rows(
        [(ids["MX"][0], "MX"), (ids["MX"][1], "MX"), (ids["CO"][0], "CO"), (ids["AR"][0], "AR")]
    )
    transactions = [
        txn_row("r-transfer", ids["MX"][0], DAY_OF["train"], txn_type="Transfer"),
        txn_row("r-deposit", ids["MX"][1], DAY_OF["train"], txn_type="Deposit"),
        txn_row("r-payment", ids["CO"][0], DAY_OF["train"], txn_type="payment"),
        txn_row("r-transfer-ar", ids["AR"][0], DAY_OF["train"], txn_type="Transfer"),
    ]
    candidates, skipped = sp.candidates_from_lakehouse(FakeLakehouse(customers, transactions))
    assert skipped == {"transaction:non-stuck-type": 1}
    drawn, _ = sp.pull_seeds(
        candidates,
        quotas={"train": {"problem_transaction": 3}, "calibration": {}, "test": {}},
        floors={"train": 0, "calibration": 0, "test": 0},
        gate=GATE,
        hard=HARD,
    )
    assert sorted(d.candidate.record_id for d in drawn["train"]) == [
        "r-payment",
        "r-transfer",
        "r-transfer-ar",
    ]


def test_complaint_routing_and_skipped_rows_counted():
    """Only Transactions-category complaints with dates become candidates."""
    test_ids = bucket_ids("test", 3, "skip")
    customers = customer_rows([(cid, "CO") for cid in test_ids])
    complaints = [
        {
            "complaint_id": "c-ok",
            "customer_id": test_ids[0],
            "creation_date": DAY_OF["test"],
            "category": "Transactions",
            "status": "Open",
            "sla_breached": False,
        },
        {
            "complaint_id": "c-wrong-cat",
            "customer_id": test_ids[1],
            "creation_date": DAY_OF["test"],
            "category": "Fees",
            "status": "Open",
            "sla_breached": False,
        },
        {
            "complaint_id": "c-no-date",
            "customer_id": test_ids[2],
            "creation_date": None,
            "category": "Transactions",
            "status": "Open",
            "sla_breached": False,
        },
    ]
    transactions = [
        txn_row("r-no-customer", "ghost-customer", DAY_OF["test"]),
        {**txn_row("r-no-date", test_ids[0], DAY_OF["test"]), "transaction_date": None},
        {**txn_row("r-bad-status", test_ids[0], DAY_OF["test"]), "transaction_status": "Mystery"},
    ]
    candidates, skipped = sp.candidates_from_lakehouse(
        FakeLakehouse(customers, transactions, complaints)
    )
    assert [c.record_id for c in candidates] == ["c-ok"]
    assert skipped["complaint:outside-category"] == 1
    assert skipped["complaint:missing-date"] == 1
    assert skipped["transaction:unknown-customer-or-country"] == 1
    assert skipped["transaction:missing-date"] == 1
    assert skipped["transaction:unexpected-status"] == 1
    assert candidates[0].sla_state == "within_sla"


def test_other_customer_probes_stay_in_split():
    """A share of transaction draws is re-roled as same-split access probes."""
    per_variant = {"problem_transaction": 10}
    customers, transactions, _ = rich_split_fixture("train", "probe", per_variant)
    candidates, _ = sp.candidates_from_lakehouse(
        FakeLakehouse(customer_rows(customers), transactions)
    )
    drawn, _ = sp.pull_seeds(
        candidates,
        quotas={
            "train": {"problem_transaction": 30},
            "calibration": {},
            "test": {},
        },
        floors={"train": 0, "calibration": 0, "test": 0},
        gate=GATE,
        hard=HARD,
    )
    probes = [d for d in drawn["train"] if d.kind == "other_customer"]
    assert len(probes) == 2  # 5% of 30 transaction draws, rounded
    assert all(d.split == "train" for d in probes)


def test_pool_and_drawn_mix_reported_side_by_side():
    """The report carries the natural outcome mix before and after the draw."""
    customers, transactions, _ = rich_split_fixture("test", "mix", {"problem_transaction": 3})
    candidates, _ = sp.candidates_from_lakehouse(
        FakeLakehouse(customer_rows(customers), transactions)
    )
    _, report = sp.pull_seeds(
        candidates,
        quotas={"train": {}, "calibration": {}, "test": {"problem_transaction": 9}},
        floors={"train": 0, "calibration": 0, "test": 0},
        gate=GATE,
        hard=HARD,
    )
    assert report.pool_status_mix["test"] == {"Declined": 3, "Pending": 3, "Reversed": 3}
    assert report.drawn_status_mix["test"] == {"Declined": 3, "Pending": 3, "Reversed": 3}


def test_missing_fraud_flag_counted_not_coerced():
    """A transaction without is_fraud is skipped, never defaulted to False."""
    train_ids = bucket_ids("train", 2, "fraudnone")
    customers = customer_rows([(cid, "MX") for cid in train_ids])
    flagged = txn_row("r-flagged", train_ids[0], DAY_OF["train"])
    unflagged = {**txn_row("r-unflagged", train_ids[1], DAY_OF["train"]), "is_fraud": None}
    candidates, skipped = sp.candidates_from_lakehouse(
        FakeLakehouse(customers, [flagged, unflagged])
    )
    assert [c.record_id for c in candidates] == ["r-flagged"]
    assert skipped == {"transaction:missing-fraud-flag": 1}


def test_missing_sla_counted_not_defaulted():
    """A complaint without sla_breached is skipped, never assumed within SLA."""
    test_ids = bucket_ids("test", 2, "slanone")
    customers = customer_rows([(cid, "CO") for cid in test_ids])
    complaints = [
        complaint_row("c-ok", test_ids[0], DAY_OF["test"]),
        {**complaint_row("c-no-sla", test_ids[1], DAY_OF["test"]), "sla_breached": None},
    ]
    candidates, skipped = sp.candidates_from_lakehouse(FakeLakehouse(customers, [], complaints))
    assert [c.record_id for c in candidates] == ["c-ok"]
    assert skipped == {"complaint:missing-sla": 1}


def test_duplicate_ids_refused_and_first_customer_wins():
    """Duplicate record ids are refused; a second row per customer is skipped."""
    train_ids = bucket_ids("train", 2, "dedup")
    customers = customer_rows([(cid, "MX") for cid in train_ids])
    transactions = [
        txn_row("r-1", train_ids[0], DAY_OF["train"]),
        txn_row("r-1", train_ids[1], DAY_OF["train"]),
        txn_row("r-2", train_ids[0], DAY_OF["train"]),
    ]
    candidates, skipped = sp.candidates_from_lakehouse(FakeLakehouse(customers, transactions))
    assert [c.record_id for c in candidates] == ["r-1"]
    assert skipped["transaction:duplicate-id"] == 1
    assert skipped["transaction:duplicate-customer"] == 1


def test_unknown_enums_rejected_and_counted():
    """Unknown transaction types, channels and complaint statuses never draw."""
    test_ids = bucket_ids("test", 4, "enums")
    customers = customer_rows([(cid, "AR") for cid in test_ids])
    transactions = [
        {**txn_row("r-bad-type", test_ids[0], DAY_OF["test"]), "transaction_type": "Bribe"},
        {**txn_row("r-bad-channel", test_ids[1], DAY_OF["test"]), "channel": "Pigeon"},
        {**txn_row("r-no-type", test_ids[2], DAY_OF["test"]), "transaction_type": None},
    ]
    complaints = [
        {**complaint_row("c-bad-status", test_ids[3], DAY_OF["test"]), "status": "Haunted"}
    ]
    candidates, skipped = sp.candidates_from_lakehouse(
        FakeLakehouse(customers, transactions, complaints)
    )
    assert candidates == []
    assert skipped["transaction:unexpected-type"] == 1
    assert skipped["transaction:unexpected-channel"] == 1
    assert skipped["transaction:missing-type"] == 1
    assert skipped["complaint:unexpected-status"] == 1


def test_band_for_only_banded_transactions():
    """Band helper returns the P6 band, or None when no amount grounds it."""
    assert (
        sp.band_for(
            sp.SeedCandidate(
                "r",
                "c",
                DAY_OF["train"],
                "problem_transaction",
                "MX",
                amount=4000.0,
                currency="MXN",
            ),
            GATE,
        )
        == "under_gate"
    )
    assert (
        sp.band_for(
            sp.SeedCandidate(
                "r",
                "c",
                DAY_OF["train"],
                "problem_transaction",
                "MX",
                amount=12000.0,
                currency="MXN",
            ),
            GATE,
        )
        == "over_gate"
    )
    assert sp.band_for(sp.SeedCandidate("r", "c", DAY_OF["test"], "complaint", "CO"), GATE) is None
