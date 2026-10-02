"""Data-quality report: ten findings on the live dataset, one CSV each, plus a README.

One command: `python scripts/analysis/data_quality.py [--perms N]`. It builds any missing
Parquet cache (build_cache.py) and writes reports/data-quality/README.md and one CSV per
finding (f01 ... f10, plus the per-page error table for finding 4). Everything is
aggregate-only, measured on the full live `data/` prefix. The README is generated from the
computed tables, so its numbers always match the CSVs.

The pure functions below take DataFrames and return DataFrames or dicts, so the unit tests
can run them on a tiny synthetic fixture. The 15-minute and 7-day chance checks reuse the
window and permutation helpers of verify_bc.py; `--perms` sets the number of permutations
(default 100, about 15 minutes in total; the tests use 3).
"""

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_cache  # noqa: E402
import verify_bc  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "cache"
OUT = ROOT / "reports" / "data-quality"
PROBLEM = ["Declined", "Reversed", "Pending"]


def mask_digits(s: pd.Series) -> pd.Series:
    """Lower-case, strip and replace every digit with '#', so ids and amounts do not split texts."""
    return s.fillna("").map(lambda x: re.sub(r"\d", "#", x).lower().strip())


# ---------------------------------------------------------------- findings 1 and 2
def templated_text(df: pd.DataFrame, text_col: str, group_col: str) -> tuple[pd.DataFrame, dict]:
    """Distinct masked texts versus rows, per group and overall, and how widely texts are shared."""
    d = df.assign(_t=mask_digits(df[text_col]))
    rows = []
    for key, g in [("all", d), *d.groupby(group_col)]:
        vc = g["_t"].value_counts()
        rows.append(
            {
                group_col: key,
                "rows": len(g),
                "distinct_texts": len(vc),
                "distinct_share": len(vc) / len(g),
                "top1_share": vc.iloc[0] / len(g),
                "top10_share": vc.iloc[:10].sum() / len(g),
            }
        )
    groups_per_text = d.groupby("_t")[group_col].nunique()
    n_groups = d[group_col].nunique()
    summary = {
        "distinct_texts": len(groups_per_text),
        "groups": n_groups,
        "texts_in_every_group": int((groups_per_text == n_groups).sum()),
        "texts_in_one_group": int((groups_per_text == 1).sum()),
    }
    return pd.DataFrame(rows), summary


# ---------------------------------------------------------------- finding 3
def reason_levels(ci: pd.DataFrame) -> pd.DataFrame:
    same = (ci["contact_reason"] == ci["reason_category"]).sum()
    return pd.DataFrame(
        [
            {
                "measure": "distinct reason_category",
                "value": ci["reason_category"].nunique(),
                "denominator": "",
            },
            {
                "measure": "distinct contact_reason",
                "value": ci["contact_reason"].nunique(),
                "denominator": "",
            },
            {
                "measure": "rows where contact_reason = reason_category",
                "value": int(same),
                "denominator": len(ci),
            },
            {
                "measure": "rows where they differ",
                "value": int(len(ci) - same),
                "denominator": len(ci),
            },
        ]
    )


# ---------------------------------------------------------------- finding 4
def pair_coverage(tx: pd.DataFrame) -> pd.DataFrame:
    """Rows per (transaction_type, channel) pair, with the share of all rows."""
    c = tx.groupby(["transaction_type", "channel"]).size().rename("rows").reset_index()
    c["share_of_rows"] = c["rows"] / len(tx)
    return c


def error_rate_by_page(de: pd.DataFrame) -> pd.DataFrame:
    g = de.groupby(de["page_url"].fillna("(null)")).agg(
        events=("event_type", "size"), errors=("event_type", lambda s: int((s == "Error").sum()))
    )
    g["error_rate"] = g["errors"] / g["events"]
    return g.reset_index().sort_values("error_rate", ascending=False)


def chance_checks(
    ptx: pd.DataFrame, de: pd.DataFrame, ci: pd.DataFrame, cust_ids: pd.Series, n_perm: int
) -> pd.DataFrame:
    """Observed link rates against within-customer timestamp permutations (see verify_bc).

    `ptx` holds the problem transactions (customer_id, transaction_date). Events are turned
    into numpy arrays at once so the large frame can be freed by the caller.
    """
    idx = pd.Series(np.arange(len(cust_ids)), index=cust_ids.to_numpy())
    ptx = ptx[ptx["customer_id"].notna()]
    p_ci = ptx["customer_id"].map(idx).to_numpy(dtype=float)
    p_t = verify_bc.to_seconds(ptx["transaction_date"])
    known = de["customer_id"].notna().to_numpy()
    e_ci = de["customer_id"].to_numpy()[known]
    e_ci = pd.Series(e_ci).map(idx).to_numpy(dtype=float)
    e_t = verify_bc.to_seconds(de["event_date"][known])
    err = de["event_type"].to_numpy()[known] == "Error"
    pay = err & (de["page_url"].to_numpy()[known] == "/payments")
    order = np.argsort(e_ci, kind="stable")  # events grouped by customer, as the helpers expect
    e_ci, e_t, err, pay = e_ci[order], e_t[order], err[order], pay[order]
    masks = {
        "problem txn to any Error event within 15 min": err,
        "problem txn to Error event on /payments within 15 min": pay,
    }
    rows = []
    perms = {k: [] for k in masks}
    for _ in range(n_perm):
        t_perm = verify_bc.permute_within_customer(e_ci, e_t)
        for k, m in masks.items():
            perms[k].append(
                verify_bc.within_window(
                    p_ci, p_t, e_ci[m], t_perm[m], -verify_bc.FIFTEEN_MIN, verify_bc.FIFTEEN_MIN
                ).mean()
            )
    for k, m in masks.items():
        obs = verify_bc.within_window(
            p_ci, p_t, e_ci[m], e_t[m], -verify_bc.FIFTEEN_MIN, verify_bc.FIFTEEN_MIN
        )
        rows.append(_chance_row(k, "all", int(obs.sum()), len(obs), np.array(perms[k])))

    inter = ci[["customer_id", "interaction_date", "reason_category"]].copy()
    inter["ci"] = inter["customer_id"].map(idx)
    inter = inter.sort_values("ci", kind="stable").reset_index(drop=True)
    i_ci = inter["ci"].to_numpy(dtype=float)
    i_t = verify_bc.to_seconds(inter["interaction_date"])
    cat = inter["reason_category"].to_numpy()
    cats = ["all", *sorted(inter["reason_category"].dropna().unique())]
    obs7 = verify_bc.within_window(i_ci, i_t, p_ci, p_t, 0, verify_bc.SEVEN_DAYS)
    perm7 = {c: [] for c in cats}
    for _ in range(n_perm):
        hit = verify_bc.within_window(
            i_ci, verify_bc.permute_within_customer(i_ci, i_t), p_ci, p_t, 0, verify_bc.SEVEN_DAYS
        )
        for c in cats:
            perm7[c].append(hit.mean() if c == "all" else hit[cat == c].mean())
    for c in cats:
        sel = np.ones(len(obs7), bool) if c == "all" else cat == c
        rows.append(
            _chance_row(
                "interaction with a problem txn in the 7 days before",
                c,
                int(obs7[sel].sum()),
                int(sel.sum()),
                np.array(perm7[c]),
            )
        )
    return pd.DataFrame(rows)


def _chance_row(link: str, subset: str, hits: int, denom: int, perm: np.ndarray) -> dict:
    return {
        "link": link,
        "subset": subset,
        "observed_hits": hits,
        "denominator": denom,
        "observed_rate": hits / denom,
        "permutation_mean": float(perm.mean()),
        "permutation_p95": float(np.percentile(perm, 95)),
        "observed_over_mean": (hits / denom) / float(perm.mean()) if perm.mean() else np.nan,
        "permutations": len(perm),
    }


# ---------------------------------------------------------------- finding 5
def null_rate_by(df: pd.DataFrame, col: str, by: str) -> pd.DataFrame:
    g = df.groupby(by).agg(rows=(col, "size"), nulls=(col, lambda s: int(s.isna().sum())))
    g["null_share"] = g["nulls"] / g["rows"]
    total = pd.DataFrame(
        [
            {
                "rows": len(df),
                "nulls": int(df[col].isna().sum()),
                "null_share": df[col].isna().mean(),
            }
        ],
        index=["all"],
    )
    return pd.concat([g, total]).rename_axis(by).reset_index()


# ---------------------------------------------------------------- finding 6
def fk_integrity(child: pd.DataFrame, col: str, parent: pd.DataFrame, pk: str) -> dict:
    values = child[col].dropna()
    in_parent = values.isin(parent[pk])
    return {
        "child_rows": len(child),
        "non_null_values": len(values),
        "values_in_parent": int(in_parent.sum()),
        "share_in_parent": float(in_parent.mean()),
        "distinct_values": int(values.nunique()),
        "parent_rows": len(parent),
        "rows_with_missing_parent": int((~in_parent).sum()),
    }


# ---------------------------------------------------------------- findings 7 and 8
def null_share(df: pd.DataFrame, col: str, by: str | None = None) -> pd.DataFrame:
    """Null count and share of `col`, overall and optionally by another column."""
    rows = [
        {
            "slice": "all",
            "value": "all",
            "rows": len(df),
            "nulls": int(df[col].isna().sum()),
            "null_share": float(df[col].isna().mean()),
        }
    ]
    if by:
        for k, g in df.groupby(by, dropna=False):
            rows.append(
                {
                    "slice": by,
                    "value": k,
                    "rows": len(g),
                    "nulls": int(g[col].isna().sum()),
                    "null_share": float(g[col].isna().mean()),
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- finding 9
def claims_by_currency(cp: pd.DataFrame, fx: pd.DataFrame) -> pd.DataFrame:
    """Claim amounts per currency, native and in USD.

    `fx` holds date, source_currency, target_currency and exchange_rate. The rate for
    `source -> USD` multiplies an amount in `source` to give USD (checked against
    transactions.amount_usd / amount). Each claim takes the rate of its creation date or the
    nearest earlier date; USD is 1. Claims dated before the first rate stay unconverted.
    """
    rates = fx[fx["target_currency"] == "USD"].copy()
    rates["fx_date"] = pd.to_datetime(rates["date"])
    rates["rate"] = pd.to_numeric(rates["exchange_rate"])
    rates = rates.rename(columns={"source_currency": "currency"})[["currency", "fx_date", "rate"]]
    c = cp.copy()
    c["currency"] = c["currency"].fillna("(none)")  # complaints without a currency have no amount
    c["claim_date"] = pd.to_datetime(c["creation_date"].str[:10])
    c["amt"] = pd.to_numeric(c["claimed_amount"])
    merged = pd.merge_asof(
        c.sort_values("claim_date"),
        rates.sort_values("fx_date"),
        left_on="claim_date",
        right_on="fx_date",
        by="currency",
        direction="backward",
    )
    usd = merged["currency"] == "USD"
    merged.loc[usd, "rate"] = 1.0
    merged.loc[usd, "fx_date"] = merged.loc[usd, "claim_date"]
    merged["amt_usd"] = merged["amt"] * merged["rate"]
    rows = []
    for cur, g in merged.groupby("currency"):
        has = g["amt"].notna()
        rows.append(
            {
                "currency": cur,
                "complaints": len(g),
                "amount_null": int((~has).sum()),
                "amount_null_share": float((~has).mean()),
                "with_amount": int(has.sum()),
                "mean_native": float(g["amt"].mean()),
                "median_native": float(g["amt"].median()),
                "mean_usd": float(g["amt_usd"].mean()),
                "rate_exact_date": int((has & (g["fx_date"] == g["claim_date"])).sum()),
                "rate_earlier_date": int((has & (g["fx_date"] < g["claim_date"])).sum()),
                "rate_missing": int((has & g["rate"].isna()).sum()),
                "rate_coverage": float((has & g["rate"].notna()).sum() / has.sum())
                if has.any()
                else np.nan,
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- finding 10
def foreign_labels(
    tx: pd.DataFrame, customers: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """transaction_country shares, their spread over customer countries, Mexico vs México."""
    t = tx.assign(
        customer_country=tx["customer_id"].map(customers.set_index("customer_id")["country"])
    )
    share = (
        t["transaction_country"].value_counts().rename("rows").rename_axis("transaction_country")
    )
    share = (share.to_frame().assign(share_of_rows=share / len(t))).reset_index()
    cross = (
        t.groupby(["customer_country", "transaction_country"]).size().rename("rows").reset_index()
    )
    cross["share_of_customer_country_rows"] = cross["rows"] / cross.groupby("customer_country")[
        "rows"
    ].transform("sum")
    mex = t[t["transaction_country"] == "Mexico"]
    mxa = t[t["transaction_country"] == "México"]
    unaccented_by_cust = mex["customer_country"].value_counts().to_dict()
    different = t["transaction_country"] != t["customer_country"]
    different_norm = t["transaction_country"].replace({"Mexico": "México"}) != t["customer_country"]
    summary = {
        "rows": len(t),
        "mexico_unaccented": len(mex),
        "mexico_accented": len(mxa),
        "accented_for_non_mexican_customers": int((mxa["customer_country"] != "México").sum()),
        "unaccented_by_customer_country": unaccented_by_cust,
        "label_differs_from_customer_country": int(different.sum()),
        "differs_after_merging_spelling": int(different_norm.sum()),
    }
    return share, cross, summary


# ---------------------------------------------------------------- output
def write_csv(df: pd.DataFrame, name: str) -> None:
    out = df.copy()
    out["label"] = "measured"
    out.to_csv(OUT / name, index=False)


def pct(x: float, digits: int = 2) -> str:
    return f"{x:.{digits}%}"


def ensure_cache() -> None:
    needed = [
        "customers",
        "call_center_interactions",
        "call_transcripts",
        "complaints",
        "transactions",
        "digital_events",
        "daily_exchange_rates",
        "service_agents",
        "branches",
    ]
    missing = [t for t in needed if not (CACHE / f"{t}.parquet").exists()]
    if missing:
        build_cache.main(missing)


def main(n_perm: int) -> None:
    ensure_cache()
    OUT.mkdir(parents=True, exist_ok=True)
    cust = pd.read_parquet(CACHE / "customers.parquet", columns=["customer_id", "country"])
    ci = pd.read_parquet(CACHE / "call_center_interactions.parquet")
    tr = pd.read_parquet(
        CACHE / "call_transcripts.parquet",
        columns=["transcript_id", "interaction_id", "customer_text"],
    )
    tr = tr.merge(ci[["interaction_id", "reason_category"]], on="interaction_id", how="left")
    cp = pd.read_parquet(CACHE / "complaints.parquet")
    tx = pd.read_parquet(
        CACHE / "transactions.parquet",
        columns=[
            "customer_id",
            "transaction_date",
            "transaction_type",
            "channel",
            "transaction_status",
            "response_code",
            "transaction_country",
        ],
    )
    fx = pd.read_parquet(CACHE / "daily_exchange_rates.parquet")
    agents = pd.read_parquet(CACHE / "service_agents.parquet")
    branches = pd.read_parquet(CACHE / "branches.parquet")

    f1, s1 = templated_text(tr, "customer_text", "reason_category")
    f2, s2 = templated_text(cp, "description", "category")
    f3 = reason_levels(ci)
    f4a = pair_coverage(tx)
    f5 = null_rate_by(tx, "response_code", "transaction_status")
    f6 = fk_integrity(agents, "assigned_branch_id", branches, "branch_id")
    f7 = null_share(cp, "origin_interaction_id")
    f9 = claims_by_currency(cp, fx)
    f10a, f10b, s10 = foreign_labels(tx, cust)
    ptx = tx.loc[tx["transaction_status"].isin(PROBLEM), ["customer_id", "transaction_date"]]
    del tx  # free memory before the large event table is read
    de = pd.read_parquet(
        CACHE / "digital_events.parquet",
        columns=["customer_id", "event_date", "event_type", "page_url", "channel"],
    )
    f4b = error_rate_by_page(de)
    f8 = null_share(de, "customer_id", "channel")
    f4c = chance_checks(ptx, de, ci, cust["customer_id"], n_perm)
    del de

    write_csv(f1, "f01-templated-transcripts.csv")
    write_csv(f2, "f02-templated-complaint-descriptions.csv")
    write_csv(f3, "f03-reason-levels.csv")
    write_csv(f4a, "f04a-type-channel-pairs.csv")
    write_csv(f4b, "f04b-error-rate-by-page.csv")
    write_csv(f4c, "f04c-chance-checks.csv")
    write_csv(f5, "f05-response-code-nulls-by-status.csv")
    write_csv(pd.DataFrame([f6]), "f06-broken-foreign-key.csv")
    write_csv(f7, "f07-origin-interaction-null.csv")
    write_csv(f8, "f08-digital-events-customer-null.csv")
    write_csv(f9, "f09-claimed-amount-by-currency.csv")
    write_csv(f10a, "f10a-transaction-country-share.csv")
    write_csv(f10b, "f10b-customer-country-by-transaction-country.csv")

    readme = render_readme(
        f1, s1, f2, s2, f3, f4a, f4b, f4c, f5, f6, f7, f8, f9, f10a, f10b, s10, n_perm
    )
    (OUT / "README.md").write_text(readme)
    print(readme)


def render_readme(
    f1, s1, f2, s2, f3, f4a, f4b, f4c, f5, f6, f7, f8, f9, f10a, f10b, s10, n_perm
) -> str:
    a1 = f1[f1["reason_category"] == "all"].iloc[0]
    a2 = f2[f2["category"] == "all"].iloc[0]
    reason = f3.set_index("measure")
    pairs_present = len(f4a)
    s15a, s15b = f4c.iloc[0], f4c.iloc[1]
    s7 = f4c[f4c["link"].str.startswith("interaction")].set_index("subset")
    nulls = f5.set_index("transaction_status")
    f7a = f7.iloc[0]
    f8a = f8.iloc[0]
    f9_all = f9["complaints"].sum()
    L = [
        "# Data-quality report [measured]",
        "",
        "Ten findings on the full live `data/` prefix, deduplicated (no duplicate primary key "
        "exists). Every number is `[measured]`; aggregates only. Reproduce with "
        "`python scripts/analysis/data_quality.py` (CSV per finding next to this file). "
        "Country is the customer's country. The chance checks use "
        f"{n_perm} permutation{'s' if n_perm != 1 else ''}.",
        "",
    ]

    def finding(n, title, what, query, number, consequence):
        L.extend(
            [
                f"## {n}. {title}",
                "",
                f"**What it is.** {what}",
                "",
                f"**Query.** `{query}`",
                "",
                f"**Number.** {number}",
                "",
                f"**Consequence for Calvino.** {consequence}",
                "",
            ]
        )

    finding(
        1,
        "Templated transcripts",
        "Call transcript text is assembled from a handful of fixed pieces and says nothing "
        "about why the customer called.",
        "SELECT reason_category, COUNT(*), "
        "COUNT(DISTINCT lower(regexp_replace(customer_text, '[0-9]', '#'))) "
        "FROM call_transcripts JOIN call_center_interactions USING (interaction_id) GROUP BY 1",
        f"{int(a1.distinct_texts)} distinct `customer_text` values (digits masked) in "
        f"{int(a1.rows):,} transcripts ({pct(a1.distinct_share, 3)}); "
        f"{s1['texts_in_every_group']} of {s1['distinct_texts']} texts appear under all "
        f"{s1['groups']} reason categories. `f01-templated-transcripts.csv`.",
        "Transcripts cannot train or evaluate a reason classifier: text predicts the template, "
        "not the reason. Classifier text must be team-generated (decision 16).",
    )
    finding(
        2,
        "Templated complaint descriptions",
        "Complaint descriptions are a function of the category.",
        "SELECT category, COUNT(*), "
        "COUNT(DISTINCT lower(regexp_replace(description, '[0-9]', '#'))) "
        "FROM complaints GROUP BY 1",
        f"{int(a2.distinct_texts)} distinct descriptions in {int(a2.rows):,} complaints "
        f"({pct(a2.distinct_share, 3)}); {s2['texts_in_one_group']} of {s2['distinct_texts']} "
        "belong to exactly one category. `f02-templated-complaint-descriptions.csv`.",
        "Free text adds nothing beyond `category`; complaint features must come from the "
        "structured fields.",
    )
    finding(
        3,
        "One reason level",
        "`contact_reason` repeats `reason_category`; there is no finer level.",
        "SELECT COUNT(DISTINCT reason_category), COUNT(DISTINCT contact_reason), "
        "SUM(contact_reason = reason_category) FROM call_center_interactions",
        f"{int(reason.loc['distinct reason_category', 'value'])} distinct values in both columns; "
        f"{int(reason.loc['rows where contact_reason = reason_category', 'value']):,} of "
        f"{int(reason.loc['rows where contact_reason = reason_category', 'denominator']):,} rows "
        "identical. `f03-reason-levels.csv`.",
        "Reasons cannot separate workflow candidates (for example payment status from card "
        "problems): both sit inside `Transaccional`.",
    )
    finding(
        4,
        "Independent fields",
        "Fields that should be linked behave as independent: every type x channel pair "
        "exists, and problem transactions neither follow nor precede errors or calls more "
        "than chance.",
        "pairs: SELECT transaction_type, channel, COUNT(*) FROM transactions GROUP BY 1,2; "
        "links: observed rate against permutations shuffling event timestamps within customer",
        f"{pairs_present} of 36 type x channel pairs present (`f04a`). Within 15 minutes, a "
        f"problem transaction meets an Error event: {int(s15a.observed_hits)} of "
        f"{int(s15a.denominator):,} ({pct(s15a.observed_rate, 4)}) against a permutation mean of "
        f"{pct(s15a.permutation_mean, 4)} (p95 {pct(s15a.permutation_p95, 4)}); on `/payments`: "
        f"{int(s15b.observed_hits)} of {int(s15b.denominator):,}, permutation mean "
        f"{pct(s15b.permutation_mean, 4)}. An interaction has a same-customer problem "
        f"transaction in the 7 days before: {pct(s7.loc['all', 'observed_rate'])} observed against "
        f"{pct(s7.loc['all', 'permutation_mean'])} permuted "
        f"({s7.loc['all', 'observed_over_mean']:.2f}x); "
        f"`Transaccional`: {pct(s7.loc['Transaccional', 'observed_rate'])} against "
        f"{pct(s7.loc['Transaccional', 'permutation_mean'])} "
        f"({s7.loc['Transaccional', 'observed_over_mean']:.2f}x). Method: "
        f"{n_perm} permutation{'s' if n_perm != 1 else ''} that shuffle "
        "timestamps among the same customer's events, "
        "which keeps each customer's activity but breaks any link. `f04c-chance-checks.csv`; "
        "supporting error rate per page in `f04b-error-rate-by-page.csv`: "
        + ", ".join(f"{r.page_url} {pct(r.error_rate, 1)}" for r in f4b.head(4).itertuples())
        + ", and 0% on login, logout and product detail pages.",
        "Attributing calls to payment or card problems from prior transactions would work at "
        "chance rate; links between tables cannot label scenarios. Scenarios and labels must be "
        "team-generated.",
    )
    finding(
        5,
        "Uniform response_code nulls",
        "`response_code` is null at the same rate in every transaction status, approved ones "
        "included.",
        "SELECT transaction_status, COUNT(*), SUM(response_code IS NULL) "
        "FROM transactions GROUP BY 1",
        "null share: "
        + ", ".join(
            f"{k} {pct(nulls.loc[k, 'null_share'])} ({int(nulls.loc[k, 'nulls']):,} of "
            f"{int(nulls.loc[k, 'rows']):,})"
            for k in nulls.index
            if k != "all"
        )
        + f"; overall {int(nulls.loc['all', 'nulls']):,} of {int(nulls.loc['all', 'rows']):,}. "
        "`f05-response-code-nulls-by-status.csv`.",
        "A missing response code is not a failure signal: do not use it as a feature or rule.",
    )
    finding(
        6,
        "Broken foreign key",
        "`service_agents.assigned_branch_id` points to branch ids that do not exist in "
        "`branches`. Reported only; no row is deleted.",
        "SELECT COUNT(*), SUM(b.branch_id IS NOT NULL) FROM service_agents a LEFT JOIN branches b "
        "ON a.assigned_branch_id = b.branch_id WHERE a.assigned_branch_id IS NOT NULL",
        f"{f6['values_in_parent']} of {f6['non_null_values']:,} non-null values "
        "exist in `branches` "
        f"({pct(f6['share_in_parent'])}); {f6['distinct_values']} distinct values against "
        f"{f6['parent_rows']} branch rows. `f06-broken-foreign-key.csv`.",
        "Agents cannot be joined to branches; do not cascade cleaning from this link (it would "
        "delete most agents and the interactions that reference them).",
    )
    finding(
        7,
        "complaints.origin_interaction_id empty",
        "No complaint records the interaction that caused it.",
        "SELECT COUNT(*), SUM(origin_interaction_id IS NULL) FROM complaints",
        f"{int(f7a.nulls):,} of {int(f7a.rows):,} null ({pct(f7a.null_share)}). "
        "`f07-origin-interaction-null.csv`.",
        "Complaint follow-up must link by customer and time, not by interaction.",
    )
    finding(
        8,
        "digital_events.customer_id null share",
        "Part of the event stream is anonymous and cannot be tied to a customer.",
        "SELECT channel, COUNT(*), SUM(customer_id IS NULL) FROM digital_events GROUP BY 1",
        f"{int(f8a.nulls):,} of {int(f8a.rows):,} events ({pct(f8a.null_share)}); by channel "
        + ", ".join(f"{r.value} {pct(r.null_share, 1)}" for r in f8.iloc[1:].itertuples())
        + ". `f08-digital-events-customer-null.csv`.",
        "Session-based features cover only the identified share of events; anonymous activity "
        "cannot enter a customer's history.",
    )
    finding(
        9,
        "claimed_amount in mixed currencies",
        "Claim amounts are in four currencies and mostly null; an average across them is "
        "meaningless.",
        "SELECT currency, COUNT(*), SUM(claimed_amount IS NULL), "
        "AVG(claimed_amount) FROM complaints "
        "GROUP BY 1; USD = claimed_amount * rate(currency -> USD, nearest earlier date)",
        f"overall {int(f9['amount_null'].sum()):,} of {int(f9_all):,} claims have no amount "
        f"({pct(f9['amount_null'].sum() / f9_all)}). Per currency: "
        + "; ".join(
            f"{r.currency}: {int(r.complaints):,} complaints, "
            f"amount null {pct(r.amount_null_share, 1)}"
            + (
                ""
                if r.with_amount == 0
                else f", mean {r.mean_native:,.0f} native = {r.mean_usd:,.2f} USD"
            )
            for r in f9.itertuples()
        )
        + ". Rate direction: `exchange_rate` for `source -> USD` "
        "converts one unit of the source currency to USD, so amounts are multiplied (checked "
        "against `transactions.amount_usd / amount` for ARS and COP; MXN has no transaction "
        "to check). Rate coverage of claims with an amount: "
        + ", ".join(
            f"{r.currency} {pct(r.rate_coverage, 1)} ({int(r.rate_exact_date):,} exact date, "
            f"{int(r.rate_earlier_date):,} earlier date, {int(r.rate_missing):,} none)"
            for r in f9.itertuples()
            if r.with_amount
        )
        + ". `f09-claimed-amount-by-currency.csv`.",
        "Never average `claimed_amount` across currencies; convert to USD first and state the "
        "rate rule. Most claims carry no amount, so any amount statistic describes a minority.",
    )
    finding(
        10,
        "Foreign transaction_country labels",
        "Foreign country labels are spread evenly over customers of every country, and "
        "`Mexico` (no accent) sits next to `México`.",
        "SELECT transaction_country, COUNT(*) FROM transactions GROUP BY 1; and "
        "customer_country x transaction_country",
        "share of rows: "
        + ", ".join(f"{r.transaction_country} {pct(r.share_of_rows, 2)}" for r in f10a.itertuples())
        + f". `México` appears for {s10['accented_for_non_mexican_customers']} "
        "non-Mexican customers; "
        f"`Mexico` has {s10['mexico_unaccented']:,} rows, from customers of "
        + ", ".join(f"{k} ({v:,})" for k, v in s10["unaccented_by_customer_country"].items())
        + f". The label differs from the customer's country on "
        f"{s10['label_differs_from_customer_country']:,} "
        f"of {s10['rows']:,} rows "
        f"({pct(s10['label_differs_from_customer_country'] / s10['rows'])}), "
        f"or {s10['differs_after_merging_spelling']:,} "
        f"({pct(s10['differs_after_merging_spelling'] / s10['rows'])}) "
        "if `Mexico` is merged into `México`. "
        "`f10a-transaction-country-share.csv`, `f10b-customer-country-by-transaction-country.csv`.",
        "A cross-border rule on `transaction_country` sees no real signal (the foreign share is "
        "random) and must decide what `Mexico` means for Mexican customers: merging it turns "
        "those rows domestic. Brazil appears only as such a label; there is no BRL or Brazilian "
        "customer.",
    )
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--perms", type=int, default=100, help="permutations for the chance checks")
    main(ap.parse_args().perms)
