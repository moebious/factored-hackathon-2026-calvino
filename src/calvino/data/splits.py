"""Customer and time splits for classifier work (TSD-015, T-103).

A record is usable in a split only when its customer bucket *and* its event
date agree on that split; anything else is excluded and counted in the split
report. Group attributes (country, segment, dialect) are never split inputs;
fairness slices are measured after the fact.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

Split = Literal["train", "calibration", "test"]
Window = Literal["pilot", "train", "calibration", "test"]

TRAIN_BUCKETS = range(0, 70)
CALIBRATION_BUCKETS = range(70, 85)
TEST_BUCKETS = range(85, 100)

# Date-defined windows (TSD-015 P2). The pilot window is dev-only: fixtures,
# debugging and scenario drafting, never in a published figure.
PILOT_START = date(2023, 6, 17)
PILOT_END = date(2023, 6, 30)
CALIBRATION_START = date(2025, 6, 1)
TEST_START = date(2026, 1, 1)

# Per-table event dates. Transcripts carry no event timestamp, only the
# partition date, so they split on ``process_date`` (see the inventory: the
# call_transcripts columns hold no date besides process_date).
EVENT_DATE_COLUMNS: dict[str, str] = {
    "call_center_interactions": "interaction_date",
    "transactions": "transaction_date",
    "complaints": "creation_date",
    "call_transcripts": "process_date",
}


def customer_bucket(customer_id: str) -> int:
    """Stable 0-99 bucket for one customer, reproducible with no lookup table."""
    digest = hashlib.sha256(customer_id.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


def assign_customer(customer_id: str) -> Split:
    """The split a customer belongs to by hash bucket alone (no date check)."""
    bucket = customer_bucket(customer_id)
    if bucket in TRAIN_BUCKETS:
        return "train"
    if bucket in CALIBRATION_BUCKETS:
        return "calibration"
    return "test"


def window_for(event_date: date | datetime) -> Window:
    """The window an event date falls in (pilot window included)."""
    day = event_date.date() if isinstance(event_date, datetime) else event_date
    if day < PILOT_START:
        return "train"
    if day <= PILOT_END:
        return "pilot"
    if day < CALIBRATION_START:
        return "train"
    if day < TEST_START:
        return "calibration"
    return "test"


def assign_record(customer_id: str, event_date: date | datetime) -> Split | None:
    """The usable split for one record, or None when bucket and date disagree.

    Out-of-window records are excluded from classifier work, never forced
    into a split.
    """
    customer_split = assign_customer(customer_id)
    window = window_for(event_date)
    if window == customer_split:
        return customer_split
    return None


@dataclass
class SplitReport:
    """Shares and exclusion counts for one split assignment run."""

    counts: dict[str, int] = field(default_factory=dict)
    excluded: int = 0
    total: int = 0

    @property
    def shares(self) -> dict[str, float]:
        """Achieved share per split over usable records."""
        usable = self.total - self.excluded
        if usable == 0:
            return {}
        return {s: self.counts.get(s, 0) / usable for s in ("train", "calibration", "test")}

    def to_dict(self) -> dict:
        return {
            "counts": dict(self.counts),
            "excluded": self.excluded,
            "total": self.total,
            "shares": self.shares,
            "windows": {
                "pilot": [PILOT_START.isoformat(), PILOT_END.isoformat()],
                "train_before": CALIBRATION_START.isoformat(),
                "test_from": TEST_START.isoformat(),
            },
        }


def build_report(records: list[tuple[str, date | datetime]]) -> SplitReport:
    """Assign every (customer_id, event_date) pair and count the outcome."""
    report = SplitReport(total=len(records))
    for customer_id, event_date in records:
        split = assign_record(customer_id, event_date)
        if split is None:
            report.excluded += 1
        else:
            report.counts[split] = report.counts.get(split, 0) + 1
    return report
