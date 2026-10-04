"""Synthetic, offline tests for the T-104 category-level baseline statistics."""

from __future__ import annotations

import pytest

from calvino.data.baseline_metrics import Baseline, ComplaintSlice, Share
from calvino.data.inventory_access import InventoryError


def cell(rows: list[dict], population: str, kind: str, value: str, metric: str) -> dict:
    return next(
        row
        for row in rows
        if (row["population"], row["slice_type"], row["slice_value"], row["metric"])
        == (population, kind, value, metric)
    )


def example() -> Baseline:
    baseline = Baseline()
    baseline.load_customers(
        [
            {"customer_id": "synthetic-1", "country": "México", "segment": "Basic"},
            {"customer_id": "synthetic-2", "country": "Argentina", "segment": "Plus"},
        ]
    )
    baseline.load_fx(
        [
            {
                "date": "2024-01-01",
                "source_currency": "MXN",
                "target_currency": "USD",
                "exchange_rate": "0.05",
            },
            {
                "date": "2024-01-04",
                "source_currency": "MXN",
                "target_currency": "USD",
                "exchange_rate": "0.06",
            },
        ]
    )
    baseline.load_calls(
        [
            {
                "interaction_id": f"synthetic-call-{n}",
                "customer_id": who,
                "reason_category": reason,
                "channel": "Phone",
                "was_resolved": resolved,
                "was_escalated": escalated,
                "requires_followup": followup,
                "duration_seconds": duration,
                "wait_time_seconds": wait,
            }
            for n, who, reason, resolved, escalated, followup, duration, wait in (
                (1, "synthetic-1", "Transaccional", "true", "false", "true", "10", "5"),
                (2, "synthetic-1", "Transaccional", "", "false", "false", "", "-1"),
                (3, "synthetic-2", "Queja", "false", "true", "", "30", "15"),
            )
        ]
    )
    baseline.load_complaints(
        [
            {
                "complaint_id": f"synthetic-case-{n}",
                "customer_id": who,
                "category": category,
                "case_type": "Claim",
                "status": status,
                "sla_breached": breached,
                "resolution_days": days,
                "compensation_granted": granted,
                "claimed_amount": amount,
                "currency": currency,
                "creation_date": created,
            }
            for n, who, category, status, breached, days, granted, amount, currency, created in (
                (
                    1,
                    "synthetic-1",
                    "Transactions",
                    "Resolved",
                    "true",
                    "16",
                    "0",
                    "100",
                    "MXN",
                    "2024-01-03",
                ),
                (
                    2,
                    "synthetic-1",
                    "Transactions",
                    "Open",
                    "",
                    "",
                    "",
                    "200",
                    "MXN",
                    "2024-01-06",
                ),
                (
                    3,
                    "synthetic-2",
                    "Service",
                    "Closed",
                    "false",
                    "",
                    "",
                    "50",
                    "ARS",
                    "2024-01-03",
                ),
            )
        ]
    )
    return baseline


def test_calls_null_denominators_invalid_times_and_slices() -> None:
    rows = example().output("interactions")
    assert cell(rows, "Transaccional", "overall", "all", "fcr")["value"] == 1
    assert cell(rows, "Transaccional", "overall", "all", "fcr")["n_null_excluded"] == 1
    duration = cell(rows, "all interactions", "overall", "all", "duration_seconds_median")
    assert duration["value"] == 20
    assert duration["n_null_excluded"] == 1
    assert duration["n_valid"] == 2
    assert (
        cell(rows, "Transaccional", "overall", "all", "wait_time_seconds_mean")[
            "n_invalid_excluded"
        ]
        == 1
    )
    assert cell(rows, "all interactions", "country", "México", "fcr")["n_population"] == 2
    assert cell(rows, "all interactions", "country_x_segment", "México / Basic", "fcr")["small_n"]


def test_complaints_resolved_denominator_and_nearest_earlier_fx() -> None:
    rows = example().output("complaints")
    assert cell(rows, "Transactions", "overall", "all", "still_open_count")["value"] == 1
    assert (
        cell(rows, "Transactions", "overall", "all", "resolution_days_mean")[
            "n_unresolved_excluded"
        ]
        == 1
    )
    assert (
        cell(rows, "all complaints", "overall", "all", "resolution_days_mean")["n_null_excluded"]
        == 1
    )
    assert (
        cell(rows, "Transactions", "overall", "all", "compensation_granted_share_of_all")["value"]
        == 0.5
    )
    assert (
        cell(rows, "Transactions", "overall", "all", "compensation_granted_share_of_resolved")[
            "value"
        ]
        == 1
    )
    assert (
        cell(rows, "Transactions", "overall", "all", "claimed_amount_usd_mean")["value"] == 8.5
    )  # 100 * .05 and 200 * .06
    assert cell(rows, "all complaints", "overall", "all", "claims_without_fx")["value"] == 1
    assert cell(rows, "all complaints", "overall", "all", "claimed_amount_MXN_mean")["value"] == 150


def test_duplicate_primary_key_and_unmatched_customer_fail_closed() -> None:
    baseline = Baseline()
    with pytest.raises(InventoryError, match="duplicate"):
        baseline.load_customers(
            [
                {"customer_id": "synthetic", "country": "México", "segment": "Basic"},
                {"customer_id": "synthetic", "country": "México", "segment": "Basic"},
            ]
        )
    with pytest.raises(InventoryError, match="unmatched"):
        Baseline().load_calls(
            [
                {
                    "interaction_id": "synthetic",
                    "customer_id": "unknown",
                    "reason_category": "Queja",
                }
            ]
        )


def test_zero_denominators_do_not_turn_missing_into_zero() -> None:
    share = Share()
    share.add(None)
    assert share.row("fcr", 1)["value"] is None
    assert share.row("fcr", 1)["denominator"] == 0
    empty = ComplaintSlice()
    assert (
        next(
            row for row in empty.rows() if row["metric"] == "compensation_granted_share_of_resolved"
        )["value"]
        is None
    )


def test_exchange_rate_ties_and_usd_identity() -> None:
    baseline = Baseline()
    baseline.load_fx(
        [
            {
                "date": "2024-01-01",
                "source_currency": "MXN",
                "target_currency": "USD",
                "exchange_rate": "0.05",
            }
        ]
    )
    row = {"claimed_amount": "100", "currency": "MXN", "creation_date": "2024-01-02"}
    assert baseline._usd(row) == 5
    assert baseline._usd({**row, "creation_date": "2023-12-31"}) is None
    assert baseline._usd({**row, "currency": "USD"}) == 100
    with pytest.raises(InventoryError, match="duplicate"):
        baseline.load_fx(
            [
                {
                    "date": "2024-01-01",
                    "source_currency": "MXN",
                    "target_currency": "USD",
                    "exchange_rate": "0.06",
                }
            ]
        )
