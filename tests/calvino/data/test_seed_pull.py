"""Tests for the P2 seed-pull sampler (TSD-019, T-106).

Synthetic fixtures only: no network, GPU, keys, dataset or salt. The fake
lakehouse stands in for the live tables; customer ids are picked by hash
bucket so split placement is deterministic and offline.
"""

from __future__ import annotations

from datetime import date

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


def txn_row(record_id, customer_id, day, status="Pending", amount=4000.0, currency="MXN"):
    return {
        "transaction_id": record_id,
        "customer_id": customer_id,
        "transaction_date": day,
        "transaction_status": status,
        "transaction_type": "transfer",
        "amount": amount,
        "currency": currency,
        "is_fraud": False,
        "channel": "app",
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
        candidates, quotas={"train": 10, "calibration": 10, "test": 0}, gate=GATE, hard=HARD
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
        candidates, quotas={"train": 10, "calibration": 0, "test": 0}, gate=GATE, hard=HARD
    )
    assert [d.candidate.record_id for d in drawn["train"]] == ["r-clear"]
    assert report.excluded.get("train") == 2


def test_draw_is_variant_balanced_and_deterministic():
    """Quotas split evenly across MX/CO/AR and repeat under the same seed."""
    ids_variants = []
    for split in ("train", "calibration", "test"):
        for variant in ("MX", "CO", "AR"):
            for cid in bucket_ids(split, 8, f"bal-{variant}"):
                ids_variants.append((split, variant, cid))
    customers = customer_rows([(cid, variant) for split, variant, cid in ids_variants])
    transactions = [
        txn_row(f"r-{split}-{variant}-{i}", cid, DAY_OF[split])
        for split, variant, cid in ids_variants
        for i in (0,)
    ]
    candidates, _ = sp.candidates_from_lakehouse(FakeLakehouse(customers, transactions))
    quotas = {"train": 12, "calibration": 12, "test": 12}
    first, _ = sp.pull_seeds(candidates, quotas=quotas, gate=GATE, hard=HARD, rng_seed=7)
    second, _ = sp.pull_seeds(candidates, quotas=quotas, gate=GATE, hard=HARD, rng_seed=7)
    for split in quotas:
        assert len(first[split]) == 12
        variants = [d.candidate.country_variant for d in first[split]]
        assert sorted(variants) == ["AR"] * 4 + ["CO"] * 4 + ["MX"] * 4
        assert [d.candidate.record_id for d in first[split]] == [
            d.candidate.record_id for d in second[split]
        ]


def test_short_pool_drawn_short_and_noted_never_backfilled():
    """A thin pool draws short with a note; other kinds never fill the gap."""
    cal_ids = bucket_ids("calibration", 3, "thin")
    transactions = [txn_row("r-only", cal_ids[0], DAY_OF["calibration"])]
    complaints = [
        {
            "complaint_id": "c-1",
            "customer_id": cal_ids[1],
            "creation_date": DAY_OF["calibration"],
            "category": "Transactions",
            "status": "open",
            "sla_breached": False,
        },
        {
            "complaint_id": "c-2",
            "customer_id": cal_ids[2],
            "creation_date": DAY_OF["calibration"],
            "category": "Transactions",
            "status": "open",
            "sla_breached": True,
        },
    ]
    customers = customer_rows([(cid, "MX") for cid in cal_ids])
    candidates, _ = sp.candidates_from_lakehouse(FakeLakehouse(customers, transactions, complaints))
    drawn, report = sp.pull_seeds(
        candidates,
        quotas={"train": 0, "calibration": 24, "test": 0},
        gate=GATE,
        hard=HARD,
    )
    assert len(drawn["calibration"]) == 3
    assert any("below quota" in note for note in report.notes)
    assert report.usable_complaints["calibration"] == 2
    assert report.complaint_tight["calibration"] is True
    assert any("complaint-seed tightness" in note for note in report.notes)


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
            "status": "open",
            "sla_breached": False,
        },
        {
            "complaint_id": "c-wrong-cat",
            "customer_id": test_ids[1],
            "creation_date": DAY_OF["test"],
            "category": "Fees",
            "status": "open",
            "sla_breached": False,
        },
        {
            "complaint_id": "c-no-date",
            "customer_id": test_ids[2],
            "creation_date": None,
            "category": "Transactions",
            "status": "open",
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
    ids = [(cid, "MX") for cid in bucket_ids("train", 40, "probe")]
    customers = customer_rows(ids)
    transactions = [txn_row(f"r-{i}", cid, DAY_OF["train"]) for i, (cid, _) in enumerate(ids)]
    candidates, _ = sp.candidates_from_lakehouse(FakeLakehouse(customers, transactions))
    drawn, _ = sp.pull_seeds(
        candidates, quotas={"train": 40, "calibration": 0, "test": 0}, gate=GATE, hard=HARD
    )
    probes = [d for d in drawn["train"] if d.kind == "other_customer"]
    assert len(probes) == 2  # 5% of 40 transaction draws
    assert all(d.split == "train" for d in probes)


def test_pool_and_drawn_mix_reported_side_by_side():
    """The report carries the natural outcome mix before and after the draw."""
    ids = [(cid, "AR") for cid in bucket_ids("test", 9, "mix")]
    customers = customer_rows(ids)
    statuses = ["Declined"] * 6 + ["Pending"] * 2 + ["Approved"]
    transactions = [
        txn_row(f"r-{i}", cid, DAY_OF["test"], status=status)
        for i, ((cid, _), status) in enumerate(zip(ids, statuses, strict=True))
    ]
    candidates, _ = sp.candidates_from_lakehouse(FakeLakehouse(customers, transactions))
    _, report = sp.pull_seeds(
        candidates, quotas={"train": 0, "calibration": 0, "test": 9}, gate=GATE, hard=HARD
    )
    assert report.pool_status_mix["test"] == {"Declined": 6, "Pending": 2, "Approved": 1}
    assert report.drawn_status_mix["test"] == {"Declined": 6, "Pending": 2, "Approved": 1}


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
