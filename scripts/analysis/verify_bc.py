"""Items B and C: closest faithful definitions of the analyst's C1/C2 numbers, and chance checks.

Reads data/cache/*.parquet (see build_cache.py), writes aggregates only to
reports/contact-reasons/verify-bc-definitions-and-chance.md.

B  counts: problem transactions, payment errors in digital_events, response-code nulls,
   disputed-charge complaints and their average claim, overall and by country.
C  chance checks: (1) observed share of problem transactions with a same-customer error
   event within +-15 minutes versus 100 permutations that shuffle event timestamps within
   customer; (2) the same for Transaccional interactions with a problem transaction in
   the 7 days before, shuffling interaction timestamps within customer.

Why shuffling within customer: it keeps each customer's activity level and time span but
breaks any link between the two event streams, so it is the null "events are independent
given the customer". Customers without a customer_id (anonymous web sessions) cannot be
matched and stay in the denominators.
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "cache"
OUT = ROOT / "reports" / "contact-reasons" / "verify-bc-definitions-and-chance.md"
PROBLEM = ["Declined", "Reversed", "Pending"]
FIFTEEN_MIN = 15 * 60
SEVEN_DAYS = 7 * 24 * 3600
N_PERM = 100
rng = np.random.default_rng(20261002)


def norm_country(s: pd.Series) -> pd.Series:
    """'Mexico' and 'México' are the same country; every other spelling is kept."""
    return s.replace({"Mexico": "México"})


def to_seconds(s: pd.Series) -> np.ndarray:
    return (pd.to_datetime(s) - pd.Timestamp("2023-01-01")).dt.total_seconds().to_numpy()


def table(rows: list[tuple], header: list[str]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return out + [""]


def pct(a: int, b: int) -> str:
    return f"{a / b:.2%}" if b else "n/a"


def within_window(cust_a, t_a, cust_b, t_b, lo, hi) -> np.ndarray:
    """For each a: is there a b of the same customer with lo <= t_a - t_b <= hi?

    Customers are folded into one sorted key (customer * BIG + seconds) so one
    searchsorted handles every customer at once; BIG exceeds the time span, so
    windows never reach another customer's block.
    """
    big = 1e9
    key_b = np.sort(cust_b * big + t_b)
    lo_k = cust_a * big + t_a - hi
    hi_k = cust_a * big + t_a - lo
    left = np.searchsorted(key_b, lo_k, side="left")
    right = np.searchsorted(key_b, hi_k, side="right")
    return right > left


def permute_within_customer(cust: np.ndarray, t: np.ndarray) -> np.ndarray:
    """Shuffle timestamps among the rows of each customer (rows sorted by customer)."""
    order = np.lexsort((rng.random(len(cust)), cust))
    return t[order]


def main() -> None:
    cust = pd.read_parquet(CACHE / "customers.parquet", columns=["customer_id", "country"])
    country_of = cust.set_index("customer_id")["country"]
    cust_idx = pd.Series(np.arange(len(cust)), index=cust["customer_id"])

    tx = pd.read_parquet(
        CACHE / "transactions.parquet",
        columns=[
            "transaction_id",
            "customer_id",
            "transaction_date",
            "transaction_type",
            "transaction_status",
            "response_code",
            "is_fraud",
            "transaction_country",
        ],
    )
    tx["country"] = tx["customer_id"].map(country_of)
    tx["problem"] = tx["transaction_status"].isin(PROBLEM)
    de = pd.read_parquet(
        CACHE / "digital_events.parquet",
        columns=[
            "event_id",
            "event_date",
            "customer_id",
            "event_type",
            "page_url",
            "action",
            "ip_country",
        ],
    )
    de["country"] = de["customer_id"].map(country_of)
    cp = pd.read_parquet(CACHE / "complaints.parquet")
    fx = pd.read_parquet(CACHE / "daily_exchange_rates.parquet")

    lines = [
        "# Items B and C: definitions, counts and chance checks [measured]",
        "",
        "Live `data/` prefix, deduplicated (no duplicate primary keys exist). "
        "Country is the customer's country unless stated.",
        "",
    ]

    # ---------------- B: C1 ----------------
    lines += [
        "## B. C1 'stuck payment'",
        "",
        "### Problem transactions",
        "",
        "Definition: `transaction_status` in (Declined, Reversed, Pending). Analyst: 4,520.",
        "",
    ]
    rows = []
    for label, d in [
        ("all types", tx),
        ("Payment or Transfer only", tx[tx.transaction_type.isin(["Payment", "Transfer"])]),
    ]:
        p = d[d.problem]
        rows.append(
            (label, f"{len(p):,}", f"{len(d):,}", pct(len(p), len(d)), f"{len(p) / 4520:.0f}x")
        )
    lines += table(rows, ["scope", "problem txns", "all txns", "share", "vs 4,520"])
    by = tx.groupby("country").agg(total=("problem", "size"), problem=("problem", "sum"))
    lines += table(
        [(c, f"{r.problem:,}", f"{r.total:,}", pct(r.problem, r.total)) for c, r in by.iterrows()],
        ["country", "problem", "all", "share"],
    )
    lines += table(
        [(s, f"{n:,}") for s, n in tx.transaction_status.value_counts().items()], ["status", "rows"]
    )

    lines += [
        "### Response-code nulls",
        "",
        "Definition: `response_code` is null. Analyst: about 2,900 (64% of 4,520).",
        "",
    ]
    nul = tx[tx.response_code.isna()]
    rows = [
        (
            s,
            f"{(nul.transaction_status == s).sum():,}",
            f"{(tx.transaction_status == s).sum():,}",
            pct((nul.transaction_status == s).sum(), (tx.transaction_status == s).sum()),
        )
        for s in ["Approved", "Declined", "Pending", "Reversed"]
    ]
    lines += table(rows, ["status", "response_code null", "status total", "null share"])
    lines += [
        f"All nulls: {len(nul):,} of {len(tx):,}; share of problem transactions with a "
        f"null: {pct(int(nul.problem.sum()), int(tx.problem.sum()))}.",
        "",
    ]

    lines += [
        "### Payment errors in digital_events",
        "",
        "No error-code or message column exists. Definitions tried: A = `event_type = "
        "'Error'` (any page); B = Error on `/payments`; C = Error with `action = "
        "'initiate_payment'`. Analyst: about 2,800.",
        "",
    ]
    er = de[de.event_type == "Error"]
    defs = {
        "A: any Error": er,
        "B: Error on /payments": er[er.page_url == "/payments"],
        "C: Error + initiate_payment": er[er.action == "initiate_payment"],
    }
    rows = [
        (k, f"{len(v):,}", f"{v.customer_id.notna().sum():,}", f"{len(v) / 2800:.0f}x")
        for k, v in defs.items()
    ]
    lines += table(rows, ["definition", "events", "with customer_id", "vs 2,800"])
    ctry = norm_country(de["ip_country"])
    rows = [
        (
            c,
            f"{((ctry == c) & (de.event_type == 'Error') & (de.page_url == '/payments')).sum():,}",
            f"{(ctry == c).sum():,}",
        )
        for c in sorted(ctry.unique())
    ]
    lines += ["Definition B by `ip_country` (spelling variants merged):", ""]
    lines += table(rows, ["ip_country", "payment errors (B)", "all events"])
    pages = de.groupby("page_url").event_type.apply(lambda s: (s == "Error").mean())
    lines += [
        "Error rate by page (share of that page's events): "
        + ", ".join(f"{k} {v:.1%}" for k, v in pages.sort_values(ascending=False).items()),
        "",
        "Errors are spread over every page, at 4.5% to 6.0% of events, so the "
        "payments page is not special.",
        "",
    ]

    # ---------------- B: C2 ----------------
    lines += [
        "## B. C2 'is this charge mine?'",
        "",
        "Definitions: D1 = category `Transactions` (subcategory 'Cargo no reconocido'); "
        "D2 = D1 and `case_type = 'Claim'`. Analyst: 297 disputed charges, "
        "average claim about 2,600.",
        "",
    ]
    cp["amt"] = pd.to_numeric(cp["claimed_amount"])
    cp["country"] = cp["customer_id"].map(country_of)
    rates = fx[fx.target_currency == "USD"][["date", "source_currency", "exchange_rate"]]
    rates = rates.rename(columns={"source_currency": "currency", "exchange_rate": "rate"})
    rates["rate"] = pd.to_numeric(rates["rate"])
    cp["date"] = cp["creation_date"].str[:10]
    cp = cp.merge(rates, how="left", on=["date", "currency"])
    cp.loc[cp.currency == "USD", "rate"] = 1.0
    cp["amt_usd"] = cp["amt"] * cp["rate"]
    d1 = cp[cp.category == "Transactions"]
    d2 = d1[d1.case_type == "Claim"]
    rows = []
    for k, d in [("D1", d1), ("D2", d2)]:
        m = d.amt.dropna()
        rows.append(
            (
                k,
                f"{len(d):,}",
                f"{len(m):,}",
                f"{m.mean():,.0f}",
                f"{m.median():,.0f}",
                f"{d.amt_usd.mean():,.0f}",
            )
        )
    lines += table(
        rows,
        [
            "definition",
            "complaints",
            "with amount",
            "mean claim (currencies mixed)",
            "median",
            "mean in USD",
        ],
    )
    rows = [
        (
            c,
            f"{len(g):,}",
            f"{g.amt.notna().sum():,}",
            f"{g.amt.mean():,.0f}",
            f"{g.amt_usd.mean():,.0f}",
        )
        for c, g in d2.groupby("currency")
    ]
    lines += [
        "D2 per currency (the 'about 2,600' figure averages MXN, COP, USD and ARS "
        "amounts as if they were one unit):",
        "",
    ]
    lines += table(rows, ["currency", "claims", "with amount", "mean (native)", "mean (USD)"])
    rows = [(c, f"{len(g):,}") for c, g in d2.groupby("country")]
    lines += table(rows, ["country (customer)", "D2 claims"])
    lines += [
        f"D2 has {len(d2):,} rows against 297 ({len(d2) / 297:.0f}x); "
        f"all categories: {len(cp):,} complaints.",
        "",
    ]

    # ---------------- C: 15-minute chance check ----------------
    lines += [
        "## C. Chance checks",
        "",
        "### Problem transaction to error event, +-15 minutes",
        "",
        "Match: a problem transaction of customer X and an `Error` event (definition A, "
        "and definition B) of the same customer within 15 minutes either way. "
        f"Null model: {N_PERM} permutations that shuffle all of a customer's event "
        "timestamps among that customer's events, then read off the Error events.",
        "",
    ]
    ptx = tx[tx.problem & tx.customer_id.notna()].copy()
    ptx["ci"] = ptx.customer_id.map(cust_idx).to_numpy()
    ptx_t = to_seconds(ptx["transaction_date"])
    ptx_ci = ptx["ci"].to_numpy(dtype=float)

    ev = de[de.customer_id.notna()].copy()
    ev["ci"] = ev.customer_id.map(cust_idx)
    ev = ev.sort_values(["ci"], kind="stable").reset_index(drop=True)
    ev_ci = ev["ci"].to_numpy(dtype=float)
    ev_t = to_seconds(ev["event_date"])
    is_err = (ev.event_type == "Error").to_numpy()
    is_err_pay = is_err & (ev.page_url == "/payments").to_numpy()

    masks = [("A: any Error", is_err), ("B: Error on /payments", is_err_pay)]
    perms = {label: [] for label, _ in masks}
    for _ in range(N_PERM):
        t_perm = permute_within_customer(ev_ci, ev_t)  # one shuffle serves both definitions
        for label, mask in masks:
            hit = within_window(ptx_ci, ptx_t, ev_ci[mask], t_perm[mask], -FIFTEEN_MIN, FIFTEEN_MIN)
            perms[label].append(hit.mean())
    rows = []
    for label, mask in masks:
        obs = within_window(ptx_ci, ptx_t, ev_ci[mask], ev_t[mask], -FIFTEEN_MIN, FIFTEEN_MIN)
        n_obs = int(obs.sum())
        perm = np.array(perms[label])
        rows.append(
            (
                label,
                f"{n_obs:,} of {len(ptx):,}",
                f"{obs.mean():.3%}",
                f"{perm.mean():.3%}",
                f"{np.percentile(perm, 95):.3%}",
                f"{obs.mean() / perm.mean():.2f}x",
            )
        )
    lines += table(
        rows,
        [
            "error definition",
            "matched problem txns",
            "observed rate",
            "permutation mean",
            "permutation p95",
            "observed / mean",
        ],
    )
    # Control: the same match for approved transactions (should look the same if no link).
    ok = tx[~tx.problem & tx.customer_id.notna()].sample(len(ptx), random_state=1)
    ok_ci = ok.customer_id.map(cust_idx).to_numpy(dtype=float)
    ok_t = to_seconds(ok["transaction_date"])
    ctrl = within_window(ok_ci, ok_t, ev_ci[is_err], ev_t[is_err], -FIFTEEN_MIN, FIFTEEN_MIN)
    lines += [
        f"Control: an equal-size random sample of Approved transactions matches an Error "
        f"event within 15 minutes at {ctrl.mean():.3%}.",
        "",
    ]

    # ---------------- C: 7-day interaction window ----------------
    lines += [
        "### Interaction to problem transaction, 7 days before",
        "",
        "Match: a same-customer problem transaction in the 7 days before the "
        "interaction. Null model: 100 permutations that shuffle interaction timestamps "
        "within customer. Compared by `reason_category`, because the attribution in "
        "TSD-006 assumes Transaccional interactions follow problem transactions.",
        "",
    ]
    ci_df = pd.read_parquet(
        CACHE / "call_center_interactions.parquet",
        columns=["interaction_id", "customer_id", "interaction_date", "reason_category"],
    )
    ci_df["ci"] = ci_df.customer_id.map(cust_idx)
    ci_df = ci_df.sort_values("ci", kind="stable").reset_index(drop=True)
    i_ci = ci_df["ci"].to_numpy(dtype=float)
    i_t = to_seconds(ci_df["interaction_date"])
    p_ci = ptx_ci
    p_t = ptx_t
    obs = within_window(i_ci, i_t, p_ci, p_t, 0, SEVEN_DAYS)
    perm_rates = {k: [] for k in ["all", *sorted(ci_df.reason_category.unique())]}
    cat = ci_df.reason_category.to_numpy()
    for _ in range(N_PERM):
        t_perm = permute_within_customer(i_ci, i_t)
        hit = within_window(i_ci, t_perm, p_ci, p_t, 0, SEVEN_DAYS)
        perm_rates["all"].append(hit.mean())
        for k in perm_rates:
            if k != "all":
                perm_rates[k].append(hit[cat == k].mean())
    rows = []
    for k in perm_rates:
        sel = np.ones(len(obs), bool) if k == "all" else cat == k
        o = obs[sel].mean()
        pr = np.array(perm_rates[k])
        rows.append(
            (
                k,
                f"{int(obs[sel].sum()):,} of {int(sel.sum()):,}",
                f"{o:.2%}",
                f"{pr.mean():.2%}",
                f"{np.percentile(pr, 95):.2%}",
                f"{o / pr.mean():.2f}x",
            )
        )
    lines += table(
        rows,
        [
            "reason_category",
            "interactions with a problem txn",
            "observed",
            "permutation mean",
            "permutation p95",
            "observed / mean",
        ],
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
