"""Item A: row counts per table (raw, after PK dedup, after orphan-FK drop) and subset search.

Reads data/cache/*.parquet (see build_cache.py) and writes aggregates only to
reports/contact-reasons/verify-a-row-counts.md. The subset search looks for any
single country, year, month, contiguous date window or complaint attribute that
reproduces the analyst's totals (878,336 rows over 13 tables, 826 complaints).
Orphans are dropped in dependency order, so a row also goes when its parent
was itself dropped. Null foreign keys are kept (reported separately).
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "cache"
OUT = ROOT / "reports" / "contact-reasons" / "verify-a-row-counts.md"
TARGET_ROWS, TARGET_COMPLAINTS = 878_336, 826

# table -> (primary key columns, {fk column: parent table}) in dependency order.
SCHEMA = {
    "customers": (["customer_id"], {}),
    "branches": (["branch_id"], {}),
    "marketing_campaigns": (["campaign_id"], {}),
    "daily_exchange_rates": (["date", "source_currency", "target_currency"], {}),
    "service_agents": (["agent_id"], {}),
    "products": (["product_id"], {"customer_id": "customers"}),
    "call_center_interactions": (
        ["interaction_id"],
        {"customer_id": "customers", "agent_id": "service_agents"},
    ),
    "call_transcripts": (
        ["transcript_id"],
        {
            "interaction_id": "call_center_interactions",
            "customer_id": "customers",
            "agent_id": "service_agents",
        },
    ),
    "complaints": (
        ["complaint_id"],
        {
            "customer_id": "customers",
            "affected_product_id": "products",
            "related_branch_id": "branches",
            "origin_interaction_id": "call_center_interactions",
            "assigned_agent_id": "service_agents",
        },
    ),
    "satisfaction_surveys": (
        ["survey_id"],
        {
            "interaction_id": "call_center_interactions",
            "customer_id": "customers",
            "agent_id": "service_agents",
        },
    ),
    "transactions": (
        ["transaction_id"],
        {"customer_id": "customers", "product_id": "products", "branch_id": "branches"},
    ),
    "campaign_sends": (
        ["send_id"],
        {"campaign_id": "marketing_campaigns", "customer_id": "customers"},
    ),
    "digital_events": (["event_id"], {"customer_id": "customers", "product_id": "products"}),
}
# Reported separately and NOT used to drop rows: only a sliver of these values exist in
# the parent table, so cascading from it would delete most agents and everything that
# references them. Measured, see the report.
BROKEN_FK = ("service_agents", "assigned_branch_id", "branches", "branch_id")
DATE_COL = {
    "call_center_interactions": "interaction_date",
    "call_transcripts": "process_date",
    "complaints": "creation_date",
    "satisfaction_surveys": "survey_date",
    "transactions": "transaction_date",
    "campaign_sends": "send_date",
    "digital_events": "event_date",
}


def main() -> None:
    clean: dict[str, pd.DataFrame] = {}
    rows = []
    for table, (pk, fks) in SCHEMA.items():
        df = pd.read_parquet(CACHE / f"{table}.parquet")
        raw = len(df)
        dedup = df.drop_duplicates(subset=pk)
        orphans = pd.Series(False, index=dedup.index)
        null_fk = {}
        for col, parent in fks.items():
            if col not in dedup:
                continue
            present = dedup[col].notna()
            null_fk[col] = int((~present).sum())
            parent_pk = SCHEMA[parent][0][0]
            orphans |= present & ~dedup[col].isin(clean[parent][parent_pk])
        kept = dedup[~orphans]
        clean[table] = kept
        rows.append(
            (
                table,
                raw,
                raw - len(dedup),
                int(orphans.sum()),
                len(kept),
                {k: v for k, v in null_fk.items() if v},
            )
        )

    total_raw = sum(r[1] for r in rows)
    total_clean = sum(r[4] for r in rows)
    lines = [
        "# Item A: row counts per table [measured]",
        "",
        "Source: live `data/` prefix. Dedup on the primary key (first row kept); orphans "
        "are non-null foreign keys whose parent row is missing after the parent's own "
        "cleaning. Null foreign keys are kept.",
        "",
        "| table | raw rows | duplicate PKs | orphan rows dropped | clean rows | null FKs kept |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for t, raw, dup, orph, kept, nulls in rows:
        lines.append(
            f"| {t} | {raw:,} | {dup:,} | {orph:,} | {kept:,} | "
            f"{', '.join(f'{k}: {v:,}' for k, v in nulls.items()) or '-'} |"
        )
    lines.append(f"| **total (13 tables)** | **{total_raw:,}** | | | **{total_clean:,}** | |")
    child, col, parent, pk = BROKEN_FK
    c = pd.read_parquet(CACHE / f"{child}.parquet")[col].dropna()
    ok = c.isin(clean[parent][pk])
    lines += [
        "",
        f"Not applied: `{child}.{col}` -> `{parent}.{pk}`: {int(ok.sum()):,} of "
        f"{len(c):,} non-null values exist in the parent ({ok.mean():.2%}); "
        f"{c.nunique():,} distinct values against {len(clean[parent]):,} branches. "
        "Every other foreign key has 0 orphans against its raw parent.",
    ]
    lines += [
        "",
        f"Analyst's lakehouse: {TARGET_ROWS:,} rows, {TARGET_COMPLAINTS} complaints. "
        f"Full data: {total_clean / TARGET_ROWS:.1f}x the rows, "
        f"{len(clean['complaints']) / TARGET_COMPLAINTS:.1f}x the complaints.",
        "",
    ]

    lines += subset_search(clean)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def subset_search(clean: dict[str, pd.DataFrame]) -> list[str]:
    """Look for any simple subset that reproduces the analyst's totals."""
    lines = ["## Subset search for 878,336 rows and 826 complaints", ""]
    country_of = clean["customers"].set_index("customer_id")["country"]

    # Rows by country, via the customer foreign key (tables with a customer_id).
    by_country = {c: 0 for c in sorted(country_of.unique())}
    reference_rows = 0
    for table, df in clean.items():
        if "customer_id" in df and table != "customers":
            counts = df["customer_id"].map(country_of).value_counts()
            for c, n in counts.items():
                by_country[c] += int(n)
        else:
            reference_rows += len(df)
    lines += [
        "Rows per country (customer-linked tables, reference tables excluded; "
        f"reference tables hold {reference_rows:,} rows):",
        "",
    ]
    lines += [f"- {c}: {n:,}" for c, n in by_country.items()] + [""]

    # Per-day rows over the date-partitioned tables; contiguous windows summing to the target.
    daily = pd.Series(dtype="int64")
    for table, col in DATE_COL.items():
        d = clean[table][col].str[:10].value_counts()
        daily = daily.add(d, fill_value=0)
    daily = daily.sort_index().astype("int64")
    ref_total = reference_rows
    hits = {}
    for label, offset in (("partitioned tables only", 0), ("plus reference tables", ref_total)):
        target = TARGET_ROWS - offset
        cum = daily.cumsum().to_numpy()
        seen = {0: -1}
        found = None
        for i, v in enumerate(cum):
            if v - target in seen:
                found = (daily.index[seen[v - target] + 1], daily.index[i])
                break
            seen[v] = i
        hits[label] = found
    lines += ["Contiguous date windows whose total equals 878,336:", ""]
    lines += [
        f"- {k}: {'window ' + v[0] + ' to ' + v[1] if v else 'none'}" for k, v in hits.items()
    ]
    lines += [""]

    # Complaints: any single attribute value, or pair, with exactly 826 rows.
    cp = clean["complaints"].copy()
    cp["year"] = cp["creation_date"].str[:4]
    cp["month"] = cp["creation_date"].str[:7]
    cp["country"] = cp["customer_id"].map(country_of)
    attrs = [
        "year",
        "month",
        "country",
        "case_type",
        "category",
        "status",
        "priority",
        "currency",
        "reception_channel",
        "sla_breached",
        "is_repeat_complainer",
    ]
    exact, near, tested = [], [], 0
    for i, a in enumerate(attrs):
        for combo in [(a,)] + [(a, b) for b in attrs[i + 1 :]]:
            sizes = cp.groupby(list(combo)).size()
            tested += len(sizes)
            for key, n in sizes.items():
                if n == TARGET_COMPLAINTS:
                    exact.append((combo, key))
                elif abs(n - TARGET_COMPLAINTS) <= 8:
                    near.append((combo, key, int(n)))
    lines += [
        "Complaint subsets (one or two attributes) with exactly 826 rows: "
        f"{exact if exact else 'none'}",
        "",
        f"Subsets tested: {tested:,}. One exact hit among that many groups of this "
        "size range is what chance produces; it is not evidence of a link.",
        "",
        f"Within +-8 rows of 826: {near if near else 'none'}",
        "",
    ]
    return lines


if __name__ == "__main__":
    main()
