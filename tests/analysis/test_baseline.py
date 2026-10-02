"""Unit tests for scripts/analysis/baseline.py on a tiny SYNTHETIC fixture.

No data files, network or model calls; every expected number is checkable by hand.
"""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "analysis" / "baseline.py"
spec = importlib.util.spec_from_file_location("baseline", SCRIPT)
bl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bl)


def cell(df, pop, stype, sval, metric):
    row = df[
        (df.population == pop)
        & (df.slice_type == stype)
        & (df.slice_value == sval)
        & (df.metric == metric)
    ]
    assert len(row) == 1
    return row.iloc[0]


def test_share_excludes_and_counts_nulls():
    v, n, n_null = bl.share(pd.Series(["True", "False", None, "True"]))
    assert (n, n_null) == (3, 1) and np.isclose(v, 2 / 3)


def test_numeric_stats_mean_median_p90_and_nulls():
    stats, n, n_null = bl.numeric_stats(pd.Series(list(range(1, 11)) + [None]))
    assert (n, n_null) == (10, 1)
    assert stats["mean"] == 5.5 and stats["median"] == 5.5
    assert np.isclose(stats["p90"], 9.1)  # linear interpolation over 1..10


def test_interactions_baseline_populations_slices_and_small_n():
    ci = pd.DataFrame(
        {
            "reason_category": ["Transaccional"] * 3 + ["Queja"] * 2,
            "country": ["AR", "AR", "CO", "AR", "CO"],
            "was_resolved": ["True", "False", "True", "True", None],
            "was_escalated": ["False"] * 5,
            "requires_followup": ["True"] * 5,
            "duration_seconds": ["100", "200", None, "300", "400"],
            "wait_time_seconds": ["10"] * 5,
        }
    )
    out = bl.interactions_baseline(ci)
    fcr_all = cell(out, "all interactions", "overall", "all", "fcr")
    assert (fcr_all.n_cases, fcr_all.n_null_excluded) == (4, 1) and fcr_all.value == 0.75
    fcr_t = cell(out, "Transaccional", "country", "AR", "fcr")
    assert fcr_t.value == 0.5 and fcr_t.n_cases == 2
    assert bool(fcr_t.small_n) is True  # fewer than 30 cases
    dur = cell(out, "all interactions", "overall", "all", "duration_seconds_median")
    assert dur.value == 250.0 and dur.n_cases == 4 and dur.n_null_excluded == 1
    assert (out["label"] == "measured").all()


def test_complaints_baseline_resolution_open_sla_and_compensation():
    cp = pd.DataFrame(
        {
            "category": ["Transactions"] * 3 + ["Fees"] * 2,
            "country": ["AR"] * 5,
            "case_type": ["Claim"] * 5,
            "status": ["Resolved", "Closed", "Open", "Rejected", "Resolved"],
            "resolution_days": ["10", None, None, None, "20"],
            "sla_breached": ["True", "False", "False", "False", "True"],
            "compensation_granted": ["50.0", None, None, None, None],
        }
    )
    out = bl.complaints_baseline(cp)
    days = cell(out, "all complaints", "overall", "all", "resolution_days_mean")
    # Resolved or Closed: 3 complaints, one of them (Closed) without a value.
    assert days.value == 15.0 and days.n_cases == 2 and days.n_null_excluded == 1
    assert cell(out, "all complaints", "overall", "all", "still_open_count").value == 1
    assert cell(out, "all complaints", "overall", "all", "sla_breached_share").value == 0.4
    comp = cell(out, "all complaints", "overall", "all", "compensation_granted_share_of_resolved")
    assert np.isclose(comp.value, 1 / 3) and comp.n_cases == 3
    tx_only = cell(out, "Transactions", "overall", "all", "still_open_count")
    assert tx_only.n_cases == 3  # slice denominator is the three Transactions complaints
    assert any(out.slice_type == "country x case_type")
