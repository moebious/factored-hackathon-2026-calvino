"""Items D and E: complaint free text diversity, and which fields the analyst's suite relies on.

Reads the downloaded CSV headers and data/cache/*.parquet (see build_cache.py) and
writes aggregates only to reports/contact-reasons/verify-de-text-and-fields.md.

D  distinct complaint `description` values (digits masked) against rows, and whether a
   value is shared across categories or case types.
E  actual columns of transactions, digital_events and complaints; a search of every
   table's columns for card, EMV/chip, 3DS, IP/geolocation and Brazil/BRL fields; and
   what the Brazil rows in transactions are.
"""

import glob
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
CACHE = DATA / "cache"
OUT = ROOT / "reports" / "contact-reasons" / "verify-de-text-and-fields.md"
TABLES = [
    "branches",
    "call_center_interactions",
    "call_transcripts",
    "campaign_sends",
    "complaints",
    "customers",
    "daily_exchange_rates",
    "digital_events",
    "marketing_campaigns",
    "products",
    "satisfaction_surveys",
    "service_agents",
    "transactions",
]
FIELD_PATTERN = re.compile(
    r"emv|chip|3ds|secure|cvv|cvc|pan\b|card|tarjeta|bin\b|ip_|geo|latitude|longitude|"
    r"brl|brazil|brasil",
    re.I,
)


def header(table: str) -> list[str]:
    files = sorted(glob.glob(str(DATA / table / "**" / "*.csv"), recursive=True))
    path = files[0] if files else str(DATA / f"{table}.csv")
    return pd.read_csv(path, encoding="utf-8-sig", nrows=0).columns.tolist()


def main() -> None:
    lines = ["# Items D and E: complaint text and the fields the suite relies on [measured]", ""]

    # ---- D ----
    cp = pd.read_parquet(CACHE / "complaints.parquet")
    masked = cp["description"].fillna("").map(lambda s: re.sub(r"\d", "#", s).lower().strip())
    n_cat = cp.assign(d=masked).groupby("d")["category"].nunique()
    n_case = cp.assign(d=masked).groupby("d")["case_type"].nunique()
    lines += [
        "## D. Complaint free text",
        "",
        "| measure | value |",
        "|---|---|",
        f"| complaints | {len(cp):,} |",
        f"| rows with a null `description` | {int(cp['description'].isna().sum()):,} |",
        f"| distinct `description` values (digits masked) | {masked.nunique():,} |",
        f"| distinct / rows | {masked.nunique() / len(cp):.3%} |",
        f"| values shared across more than one `category` | {int((n_cat > 1).sum())} of "
        f"{len(n_cat)} |",
        f"| values shared across more than one `case_type` | {int((n_case > 1).sum())} of "
        f"{len(n_case)} |",
        f"| distinct `resolution` values | {cp['resolution'].fillna('').nunique()} |",
        "",
        "Each of the five descriptions belongs to exactly one category, so the text is a "
        "function of `category` and adds no information beyond it.",
        "",
    ]

    # ---- E ----
    headers = {t: header(t) for t in TABLES}
    lines += ["## E. Columns", ""]
    for t in ["transactions", "digital_events", "complaints"]:
        lines += [
            f"**{t}** ({len(headers[t])} columns): " + ", ".join(f"`{c}`" for c in headers[t]),
            "",
        ]
    lines += [
        "### Field search over all 13 tables",
        "",
        "Column names matching card, EMV, chip, 3DS, secure, CVV, PAN, BIN, IP, geo, "
        "latitude, longitude, Brazil or BRL:",
        "",
    ]
    for t in TABLES:
        hits = [c for c in headers[t] if FIELD_PATTERN.search(c)]
        lines.append(f"- {t}: {', '.join(f'`{c}`' for c in hits) if hits else 'none'}")
    products = pd.read_parquet(CACHE / "products.parquet", columns=["product_type", "currency"])
    lines += [
        "",
        "No card table, and no EMV, chip, 3DS, CVV, PAN or BIN column in any table. "
        "Cards exist only as `products.product_type` values: "
        + ", ".join(f"`{v}`" for v in sorted(products.product_type.unique()) if "Tarjeta" in v)
        + ".",
        "",
    ]

    tx = pd.read_parquet(
        CACHE / "transactions.parquet",
        columns=["customer_id", "currency", "transaction_country", "transaction_status"],
    )
    cust = pd.read_parquet(CACHE / "customers.parquet", columns=["customer_id", "country"])
    tx["customer_country"] = tx["customer_id"].map(cust.set_index("customer_id")["country"])
    brazil = tx[tx["transaction_country"] == "Brazil"]
    problem = tx["transaction_status"].isin(["Declined", "Reversed", "Pending"])
    lines += [
        "### Brazil and BRL",
        "",
        f"- `BRL` in `transactions.currency`: {int((tx['currency'] == 'BRL').sum()):,}; "
        "currencies present in `products`: "
        + ", ".join(sorted(products.currency.unique()))
        + "; in `transactions`: "
        + ", ".join(sorted(tx.currency.unique()))
        + ".",
        "- Customer and branch countries: "
        + ", ".join(sorted(cust.country.unique()))
        + " (no Brazil).",
        f"- `Brazil` appears as `transaction_country` on {len(brazil):,} of {len(tx):,} "
        f"transactions ({len(brazil) / len(tx):.2%}), in currencies "
        + ", ".join(f"{k} {v:,}" for k, v in brazil.currency.value_counts().items())
        + ".",
        "- Cross-tab of customer country by `transaction_country` (rows):",
        "",
    ]
    ct = pd.crosstab(tx["customer_country"], tx["transaction_country"])
    lines += [
        "| customer country | " + " | ".join(ct.columns) + " |",
        "|---|" + "---:|" * len(ct.columns),
    ]
    lines += [
        f"| {idx} | " + " | ".join(f"{v:,}" for v in row) + " |" for idx, row in ct.iterrows()
    ]
    lines += [
        "",
        "Foreign countries (USA, Spain, Brazil, and the spelling variant `Mexico` next "
        "to `México`) each hold about 0.9% of transactions, spread evenly over customers "
        "of every country, and Brazil's problem-status rate is "
        f"{problem[tx['transaction_country'] == 'Brazil'].mean():.1%} against "
        f"{problem[tx['transaction_country'] != 'Brazil'].mean():.1%} elsewhere. "
        "Brazil is a label on a random foreign share, not a market in this data.",
        "",
    ]
    OUT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
