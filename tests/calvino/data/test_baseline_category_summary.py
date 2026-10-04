"""Synthetic checks for safe, accurate category reporting in T-104."""

from __future__ import annotations

from calvino.data.baseline_metrics import Baseline


def test_non_target_complaints_are_not_claimed_to_be_unknown() -> None:
    baseline = Baseline()
    baseline.load_customers([{"customer_id": "synthetic", "country": "México", "segment": "Basic"}])
    cases = [
        {
            "complaint_id": f"synthetic-{i}",
            "customer_id": "synthetic",
            "creation_date": "2024-01-01",
            "category": category,
            "case_type": "Claim",
            "status": "Open",
            "sla_breached": None,
            "resolution_days": None,
            "compensation_granted": None,
            "claimed_amount": None,
            "currency": None,
        }
        for i, category in enumerate(("Transactions", "Another valid category", None))
    ]
    baseline.load_complaints(cases)
    assert baseline.non_target["complaint_category"] == 1
    assert baseline.unknown["complaint_category_null"] == 1
    assert baseline.unknown["complaint_category"] == 0
    assert (
        next(
            row
            for row in baseline.output("complaints")
            if row["population"] == "Transactions"
            and row["slice_type"] == "overall"
            and row["metric"] == "still_open_count"
        )["n_population"]
        == 1
    )
