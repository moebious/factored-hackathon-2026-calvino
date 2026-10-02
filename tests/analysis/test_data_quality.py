"""Unit tests for scripts/analysis/data_quality.py on a tiny SYNTHETIC fixture.

No data files, network or model calls. Values are invented so each expected number can be
checked by hand.
"""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "analysis" / "data_quality.py"
spec = importlib.util.spec_from_file_location("data_quality", SCRIPT)
dq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dq)


def test_templated_text_masks_digits_and_counts_shared_texts():
    df = pd.DataFrame(
        {"txt": ["Hola 123", "hola 456", "Adios", "HOLA 999"], "grp": ["a", "b", "a", "b"]}
    )
    per_group, summary = dq.templated_text(df, "txt", "grp")
    allrow = per_group[per_group["grp"] == "all"].iloc[0]
    assert (allrow["rows"], allrow["distinct_texts"]) == (4, 2)  # 'hola ###' and 'adios'
    assert summary["texts_in_every_group"] == 1  # 'hola ###' is under both groups
    assert summary["texts_in_one_group"] == 1  # 'adios' only under 'a'


def test_reason_levels_reports_identical_columns():
    ci = pd.DataFrame({"reason_category": ["x", "y", "x"], "contact_reason": ["x", "y", "x"]})
    out = dq.reason_levels(ci).set_index("measure")["value"]
    assert out["distinct contact_reason"] == 2
    assert out["rows where they differ"] == 0


def test_pair_coverage_and_error_rate_by_page():
    tx = pd.DataFrame({"transaction_type": ["A", "A", "B"], "channel": ["x", "x", "y"]})
    pairs = dq.pair_coverage(tx)
    assert len(pairs) == 2 and pairs["rows"].sum() == 3
    de = pd.DataFrame(
        {"page_url": ["/p", "/p", None, "/q"], "event_type": ["Error", "View", "Error", "View"]}
    )
    pages = dq.error_rate_by_page(de).set_index("page_url")
    assert pages.loc["/p", "error_rate"] == 0.5
    assert pages.loc["(null)", "errors"] == 1


def test_null_rate_by_status_includes_overall_row():
    tx = pd.DataFrame(
        {"transaction_status": ["ok", "ok", "bad"], "response_code": [None, "00", "51"]}
    )
    out = dq.null_rate_by(tx, "response_code", "transaction_status").set_index("transaction_status")
    assert out.loc["ok", "null_share"] == 0.5
    assert out.loc["all", "nulls"] == 1


def test_fk_integrity_counts_values_missing_from_parent():
    child = pd.DataFrame({"b": ["b1", "zz", None, "yy"]})
    parent = pd.DataFrame({"branch_id": ["b1", "b2"]})
    out = dq.fk_integrity(child, "b", parent, "branch_id")
    assert out["non_null_values"] == 3 and out["values_in_parent"] == 1
    assert out["rows_with_missing_parent"] == 2


def test_null_share_overall_and_by_column():
    df = pd.DataFrame({"c": [None, "a", None, "b"], "g": ["x", "x", "y", "y"]})
    out = dq.null_share(df, "c", "g")
    assert out.iloc[0]["null_share"] == 0.5
    assert out[out["value"] == "y"].iloc[0]["nulls"] == 1


def test_claims_use_nearest_earlier_rate_and_usd_is_one():
    cp = pd.DataFrame(
        {
            "currency": ["ARS", "USD", None, "ARS"],
            "claimed_amount": ["1000", "50", None, "500"],
            "creation_date": [
                "2024-01-03 10:00:00",
                "2024-01-03 10:00:00",
                "2024-01-03 10:00:00",
                "2024-01-01 09:00:00",
            ],
        }
    )
    fx = pd.DataFrame(
        {
            "date": ["2024-01-01", "2024-01-02"],
            "source_currency": ["ARS", "ARS"],
            "target_currency": ["USD", "USD"],
            "exchange_rate": ["0.001", "0.002"],
        }
    )
    out = dq.claims_by_currency(cp, fx).set_index("currency")
    # 2024-01-03 has no rate: the claim takes the 2024-01-02 rate (0.002); the other the exact day.
    assert out.loc["ARS", "rate_earlier_date"] == 1 and out.loc["ARS", "rate_exact_date"] == 1
    assert np.isclose(out.loc["ARS", "mean_usd"], (1000 * 0.002 + 500 * 0.001) / 2)
    assert out.loc["USD", "mean_usd"] == 50
    assert out.loc["(none)", "amount_null_share"] == 1.0
    assert out.loc["ARS", "rate_coverage"] == 1.0


def test_foreign_labels_spelling_and_spread():
    tx = pd.DataFrame(
        {
            "customer_id": ["c1", "c1", "c2", "c2"],
            "transaction_country": ["México", "Mexico", "Colombia", "Mexico"],
        }
    )
    cust = pd.DataFrame({"customer_id": ["c1", "c2"], "country": ["México", "Colombia"]})
    share, cross, summary = dq.foreign_labels(tx, cust)
    assert share.set_index("transaction_country").loc["Mexico", "rows"] == 2
    assert summary["label_differs_from_customer_country"] == 2
    assert summary["differs_after_merging_spelling"] == 1  # only c2's 'Mexico' stays foreign
    assert summary["accented_for_non_mexican_customers"] == 0
    assert cross["rows"].sum() == 4


def test_chance_checks_on_a_hand_built_case():
    customers = pd.Series(["c1", "c2"])
    ptx = pd.DataFrame({"customer_id": ["c1"], "transaction_date": ["2024-01-01 10:00:00"]})
    de = pd.DataFrame(
        {
            "customer_id": ["c1", "c1", "c2", None],
            "event_date": [
                "2024-01-01 10:10:00",
                "2024-01-05 08:00:00",
                "2024-01-01 10:10:00",
                "2024-01-01 10:10:00",
            ],
            "event_type": ["Error", "PageView", "Error", "Error"],
            "page_url": ["/payments", "/home", "/payments", "/payments"],
        }
    )
    ci = pd.DataFrame(
        {
            "customer_id": ["c1"],
            "interaction_date": ["2024-01-02 10:00:00"],
            "reason_category": ["Transaccional"],
        }
    )
    out = dq.chance_checks(ptx, de, ci, customers, n_perm=3)
    first = out.iloc[0]
    # The problem txn has a same-customer Error 10 minutes later: observed 1 of 1.
    assert (first["observed_hits"], first["denominator"]) == (1, 1)
    seven = out[
        out["link"].str.startswith("interaction") & (out["subset"] == "Transaccional")
    ].iloc[0]
    assert (seven["observed_hits"], seven["denominator"]) == (1, 1)  # txn is 1 day before the call
    assert set(out.columns) >= {
        "observed_rate",
        "permutation_mean",
        "permutation_p95",
        "permutations",
    }
    assert (out["permutations"] == 3).all()
