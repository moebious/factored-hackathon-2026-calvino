"""Customer and time split assignment on synthetic fixtures (TSD-015, T-103)."""

from __future__ import annotations

from datetime import date

from calvino.data.splits import (
    assign_customer,
    assign_record,
    build_report,
    customer_bucket,
    window_for,
)


def _ids_in(split: str, n: int = 300) -> list[str]:
    """Synthetic customer ids hashing into one split (test helper only)."""
    found = []
    for i in range(n):
        cid = f"SYN-{split}-{i:04d}"
        if assign_customer(cid) == split:
            found.append(cid)
    return found


def test_bucket_is_deterministic_across_calls():
    assert customer_bucket("SYN-C001") == customer_bucket("SYN-C001")
    assert assign_customer("SYN-C001") == assign_customer("SYN-C001")


def test_all_three_splits_are_reachable():
    splits = {assign_customer(f"SYN-{i:05d}") for i in range(2000)}
    assert splits == {"train", "calibration", "test"}


def test_window_boundaries():
    assert window_for(date(2023, 6, 17)) == "pilot"
    assert window_for(date(2023, 6, 30)) == "pilot"
    assert window_for(date(2023, 6, 16)) == "train"
    assert window_for(date(2023, 7, 1)) == "train"
    assert window_for(date(2025, 5, 31)) == "train"
    assert window_for(date(2025, 6, 1)) == "calibration"
    assert window_for(date(2025, 12, 31)) == "calibration"
    assert window_for(date(2026, 1, 1)) == "test"


def test_record_needs_bucket_and_date_to_agree():
    train_id = _ids_in("train", 300)[0]
    assert assign_record(train_id, date(2025, 1, 15)) == "train"
    # Same customer, calibration-window date: excluded, never forced.
    assert assign_record(train_id, date(2025, 7, 15)) is None
    assert assign_record(train_id, date(2026, 2, 1)) is None


def test_pilot_window_records_are_excluded():
    train_id = _ids_in("train", 300)[0]
    assert assign_record(train_id, date(2023, 6, 20)) is None


def test_report_states_shares_and_exclusions():
    train_ids = _ids_in("train", 300)[:20]
    records = [(cid, date(2025, 3, 10)) for cid in train_ids]
    records += [(train_ids[0], date(2025, 8, 10))]  # out of window: excluded
    report = build_report(records)
    assert report.total == 21
    assert report.excluded == 1
    assert report.counts == {"train": 20}
    assert report.shares == {"train": 1.0, "calibration": 0.0, "test": 0.0}
    data = report.to_dict()
    assert data["windows"]["test_from"] == "2026-01-01"
