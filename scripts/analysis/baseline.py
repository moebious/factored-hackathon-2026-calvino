"""Independent T-104 headline baseline for interactions and complaints.

One command: `python scripts/analysis/baseline.py` (needs data/cache from build_cache.py).
Writes reports/baseline/interactions.csv, complaints.csv and README.md. Every number is
aggregate-only and measured on the full live `data/` prefix.

Definitions (also written into the README) are fixed here, before any number is read:

Interactions (`call_center_interactions`), for all interactions and for
`reason_category = 'Transaccional'`, overall and by customer country:
  fcr          share with was_resolved = true, nulls excluded and counted
  escalation   share with was_escalated = true
  follow_up    share with requires_followup = true
  duration / wait   mean, median and p90 (linear interpolation) of duration_seconds and
               wait_time_seconds over non-null values; nulls counted

Complaints (`complaints`), for all complaints and for `category = 'Transactions'`, overall
and by customer country and by case_type (and country x case_type):
  resolution_days   mean, median, p90 over complaints with status Resolved or Closed and a
                    non-null resolution_days; resolved complaints without a value counted
  still_open        count of complaints with status Open, In Process or Escalated
                    (Rejected counts as neither open nor resolved)
  sla_breached      share with sla_breached = true
  compensation      `compensation_granted` holds an amount, not a flag; granted means a
                    non-null amount. Share of all complaints in the slice, and share of
                    resolved/closed ones (amounts exist only on Resolved and Closed)

A cell is marked `small_n` when it rests on fewer than 30 cases.
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "cache"
OUT = ROOT / "reports" / "baseline"
MIN_CASES = 30
RESOLVED = ["Resolved", "Closed"]
OPEN = ["Open", "In Process", "Escalated"]
COLUMNS = [
    "population",
    "slice_type",
    "slice_value",
    "metric",
    "value",
    "n_cases",
    "n_null_excluded",
    "small_n",
    "label",
]


def _row(pop, stype, sval, metric, value, n, n_null) -> dict:
    return {
        "population": pop,
        "slice_type": stype,
        "slice_value": sval,
        "metric": metric,
        "value": value,
        "n_cases": int(n),
        "n_null_excluded": int(n_null),
        "small_n": bool(n < MIN_CASES),
        "label": "measured",
    }


def share(series: pd.Series, true_value: str = "True") -> tuple[float, int, int]:
    """Share equal to `true_value` among non-null values, plus non-null and null counts."""
    nonnull = series.dropna()
    n_null = int(series.isna().sum())
    if len(nonnull) == 0:
        return float("nan"), 0, n_null
    return float((nonnull == true_value).mean()), len(nonnull), n_null


def numeric_stats(series: pd.Series) -> tuple[dict, int, int]:
    """mean, median and p90 of the non-null numeric values, plus non-null and null counts."""
    x = pd.to_numeric(series, errors="coerce").dropna()
    n_null = int(len(series) - len(x))
    if len(x) == 0:
        return {"mean": float("nan"), "median": float("nan"), "p90": float("nan")}, 0, n_null
    return (
        {"mean": float(x.mean()), "median": float(x.median()), "p90": float(np.percentile(x, 90))},
        len(x),
        n_null,
    )


def slices(df: pd.DataFrame, by: list[str]) -> list[tuple[str, str, pd.DataFrame]]:
    """(slice_type, slice_value, rows): overall, each single attribute, and their product."""
    out = [("overall", "all", df)]
    for col in by:
        out += [(col, str(k), g) for k, g in df.groupby(col, dropna=False)]
    if len(by) == 2:
        out += [
            (f"{by[0]} x {by[1]}", f"{a} | {b}", g) for (a, b), g in df.groupby(by, dropna=False)
        ]
    return out


def interactions_baseline(ci: pd.DataFrame) -> pd.DataFrame:
    """Headline metrics for all interactions and for Transaccional, overall and by country."""
    rows = []
    for pop, d in [
        ("all interactions", ci),
        ("Transaccional", ci[ci["reason_category"] == "Transaccional"]),
    ]:
        for stype, sval, g in slices(d, ["country"]):
            for metric, col in [
                ("fcr", "was_resolved"),
                ("escalation", "was_escalated"),
                ("follow_up", "requires_followup"),
            ]:
                v, n, nn = share(g[col])
                rows.append(_row(pop, stype, sval, metric, v, n, nn))
            for col in ["duration_seconds", "wait_time_seconds"]:
                stats, n, nn = numeric_stats(g[col])
                for stat, v in stats.items():
                    rows.append(_row(pop, stype, sval, f"{col}_{stat}", v, n, nn))
    return pd.DataFrame(rows, columns=COLUMNS)


def complaints_baseline(cp: pd.DataFrame) -> pd.DataFrame:
    """Headline metrics for all complaints and for category Transactions."""
    rows = []
    for pop, d in [("all complaints", cp), ("Transactions", cp[cp["category"] == "Transactions"])]:
        for stype, sval, g in slices(d, ["country", "case_type"]):
            res = g[g["status"].isin(RESOLVED)]
            stats, n, _ = numeric_stats(res["resolution_days"])
            missing = len(res) - n
            for stat, v in stats.items():
                rows.append(_row(pop, stype, sval, f"resolution_days_{stat}", v, n, missing))
            n_open = int(g["status"].isin(OPEN).sum())
            rows.append(_row(pop, stype, sval, "still_open_count", n_open, len(g), 0))
            v, n, nn = share(g["sla_breached"])
            rows.append(_row(pop, stype, sval, "sla_breached_share", v, n, nn))
            granted = pd.to_numeric(g["compensation_granted"], errors="coerce").notna()
            rows.append(
                _row(
                    pop,
                    stype,
                    sval,
                    "compensation_granted_share_of_all",
                    float(granted.mean()) if len(g) else float("nan"),
                    len(g),
                    0,
                )
            )
            res_granted = pd.to_numeric(res["compensation_granted"], errors="coerce").notna()
            rows.append(
                _row(
                    pop,
                    stype,
                    sval,
                    "compensation_granted_share_of_resolved",
                    float(res_granted.mean()) if len(res) else float("nan"),
                    len(res),
                    0,
                )
            )
    return pd.DataFrame(rows, columns=COLUMNS)


def _fmt(metric: str, v: float) -> str:
    if pd.isna(v):
        return "n/a"
    if metric.endswith("_count"):
        return f"{int(v):,}"
    if "share" in metric or metric in ("fcr", "escalation", "follow_up"):
        return f"{v:.2%}"
    return f"{v:,.1f}"


def headline_table(df: pd.DataFrame, populations: list[str]) -> list[str]:
    """Markdown table of the overall rows plus the country rows, populations as columns."""
    d = df[df["slice_type"].isin(["overall", "country"])]
    lines = []
    metrics = list(dict.fromkeys(d["metric"]))
    header = ["metric"] + [
        f"{p} / {sv}"
        for p in populations
        for sv in dict.fromkeys(d[d.population == p]["slice_value"])
    ]
    lines += ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for m in metrics:
        cells = [m]
        for p in populations:
            for sv in dict.fromkeys(d[d.population == p]["slice_value"]):
                r = d[(d.population == p) & (d.slice_value == sv) & (d.metric == m)].iloc[0]
                flag = " (small n)" if r.small_n else ""
                cells.append(f"{_fmt(m, r.value)}{flag}, n={r.n_cases:,}")
        lines.append("| " + " | ".join(cells) + " |")
    return lines + [""]


def main() -> None:
    cust = pd.read_parquet(CACHE / "customers.parquet", columns=["customer_id", "country"])
    country_of = cust.set_index("customer_id")["country"]
    ci = pd.read_parquet(CACHE / "call_center_interactions.parquet")
    ci["country"] = ci["customer_id"].map(country_of)
    cp = pd.read_parquet(CACHE / "complaints.parquet")
    cp["country"] = cp["customer_id"].map(country_of)

    inter = interactions_baseline(ci)
    comp = complaints_baseline(cp)
    OUT.mkdir(parents=True, exist_ok=True)
    inter.to_csv(OUT / "interactions.csv", index=False)
    comp.to_csv(OUT / "complaints.csv", index=False)

    readme = [
        "# T-104 headline baseline (independent cross-check) [measured]",
        "",
        "Full live `data/` prefix; aggregates only. Reproduce with "
        "`python scripts/analysis/build_cache.py <tables>` then "
        "`python scripts/analysis/baseline.py`. Country is the customer's country "
        "(`customers.country` through `customer_id`). All numbers are `[measured]`. "
        "The CSVs hold every slice; this page shows the headline cells.",
        "",
        "## Definitions (fixed before any number was read)",
        "",
        "**Interactions** (`call_center_interactions`), for all interactions and for "
        "`reason_category = 'Transaccional'`, overall and by country:",
        "",
        "- `fcr`: share with `was_resolved = true`; nulls excluded and counted.",
        "- `escalation`: share with `was_escalated = true`.",
        "- `follow_up`: share with `requires_followup = true`.",
        "- `duration_seconds_*`, `wait_time_seconds_*`: mean, median and p90 (linear "
        "interpolation) over non-null values; nulls counted.",
        "",
        "**Complaints** (`complaints`), for all complaints and for `category = "
        "'Transactions'`, overall, by country, by `case_type` and by their product:",
        "",
        "- `resolution_days_*`: mean, median, p90 over complaints with `status` Resolved or "
        "Closed and a non-null `resolution_days`; resolved complaints without a value are "
        "counted in `n_null_excluded`.",
        "- `still_open_count`: complaints with `status` Open, In Process or Escalated "
        "(Rejected counts as neither open nor resolved); the denominator is all complaints "
        "in the slice.",
        "- `sla_breached_share`: share with `sla_breached = true`.",
        "- `compensation_granted_share_of_*`: `compensation_granted` holds an amount, not a "
        "flag, so granted means a non-null amount; shown over all complaints in the slice "
        "and over resolved/closed ones (amounts exist only on Resolved and Closed).",
        "",
        f"A cell is marked `small_n` when it rests on fewer than {MIN_CASES} cases. "
        "`n_cases` is the count the value is computed over; `n_null_excluded` counts "
        "records left out for a missing value.",
        "",
        "## Interactions",
        "",
    ]
    readme += headline_table(inter, ["all interactions", "Transaccional"])
    readme += [
        "## Complaints",
        "",
        "Overall and by country here; `case_type` and country x case_type slices are in "
        "`complaints.csv`.",
        "",
    ]
    readme += headline_table(comp, ["all complaints", "Transactions"])
    (OUT / "README.md").write_text("\n".join(readme) + "\n")
    print("\n".join(readme))


if __name__ == "__main__":
    main()
