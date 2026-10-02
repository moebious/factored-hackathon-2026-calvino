"""Unit tests for the window-matching helpers in scripts/analysis/verify_bc.py.

All inputs are tiny synthetic arrays (labelled as such); no data files, network or
model calls are needed.
"""

import importlib.util
from pathlib import Path

import numpy as np

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "analysis" / "verify_bc.py"
spec = importlib.util.spec_from_file_location("verify_bc", SCRIPT)
verify_bc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify_bc)

MIN = 60.0


def test_symmetric_window_matches_only_inside_15_minutes_of_same_customer():
    cust_a = np.array([1.0, 1.0, 1.0, 2.0])
    t_a = np.array([1000.0, 1000.0, 1000.0, 1000.0])
    cust_b = np.array([1.0, 1.0, 1.0, 3.0])
    t_b = np.array([1000.0 + 14 * MIN, 1000.0 - 15 * MIN, 1000.0 + 16 * MIN, 1000.0])
    hits = verify_bc.within_window(cust_a, t_a, cust_b, t_b, -15 * MIN, 15 * MIN)
    # Customer 1 has an event at +14 min and -15 min (inclusive); customer 2 has no
    # events at all, and customer 3's event belongs to someone else.
    assert hits.tolist() == [True, True, True, False]
    only_far = verify_bc.within_window(
        cust_a[:1], t_a[:1], cust_b[2:3], t_b[2:3], -15 * MIN, 15 * MIN
    )
    assert only_far.tolist() == [False]


def test_one_sided_window_looks_back_only():
    seven_days = 7 * 24 * 3600.0
    hits = verify_bc.within_window(
        np.array([1.0, 1.0, 1.0]),
        np.array([10 * seven_days] * 3),
        np.array([1.0, 1.0]),
        np.array([10 * seven_days - 3600.0, 10 * seven_days + 3600.0]),
        0,
        seven_days,
    )
    # The same customer has a problem 1 hour before (inside) and 1 hour after (ignored).
    assert hits.tolist() == [True, True, True]
    after_only = verify_bc.within_window(
        np.array([1.0]),
        np.array([10 * seven_days]),
        np.array([1.0]),
        np.array([10 * seven_days + 3600.0]),
        0,
        seven_days,
    )
    assert after_only.tolist() == [False]


def test_windows_do_not_leak_across_customers():
    # Customer 2 starts right where customer 1's block ends in the folded key.
    hits = verify_bc.within_window(
        np.array([2.0]), np.array([0.0]), np.array([1.0]), np.array([99.0]), -900.0, 900.0
    )
    assert hits.tolist() == [False]


def test_permutation_keeps_each_customers_timestamps():
    cust = np.array([1.0, 1.0, 1.0, 2.0, 2.0])
    t = np.array([5.0, 6.0, 7.0, 100.0, 200.0])
    shuffled = verify_bc.permute_within_customer(cust, t)
    assert sorted(shuffled[:3]) == [5.0, 6.0, 7.0]
    assert sorted(shuffled[3:]) == [100.0, 200.0]


def test_country_spelling_variants_are_merged():
    import pandas as pd

    out = verify_bc.norm_country(pd.Series(["Mexico", "México", "Brazil"]))
    assert out.tolist() == ["México", "México", "Brazil"]
