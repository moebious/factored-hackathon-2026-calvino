"""Convert the downloaded CSV tables in data/ to one Parquet file per table.

Usage: python scripts/analysis/build_cache.py TABLE [TABLE ...]

Output goes to data/cache/<table>.parquet (git-ignored). Everything is read as
text with the UTF-8 BOM stripped (every source file starts with one), and a
`_n_files` / `_src_rows` summary is printed so raw row counts are known before
any deduplication. Only the columns the verification scripts need are kept for
the two large tables, so the cache stays small.
"""

import glob
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2] / "data"
CACHE = ROOT / "cache"

# Columns kept for the big tables; None keeps everything.
KEEP = {
    "digital_events": [
        "event_id",
        "event_date",
        "customer_id",
        "session_id",
        "event_type",
        "event_category",
        "channel",
        "platform",
        "page_url",
        "page_title",
        "action",
        "element_id",
        "product_id",
        "event_value",
        "ip_country",
    ],
    "transactions": None,
    "call_transcripts": [
        "transcript_id",
        "interaction_id",
        "customer_id",
        "agent_id",
        "process_date",
        "customer_text",
    ],
    "campaign_sends": ["send_id", "campaign_id", "customer_id", "send_date"],
}


def source_files(table: str) -> list[str]:
    files = sorted(glob.glob(str(ROOT / table / "**" / "*.csv"), recursive=True))
    return files or [str(ROOT / f"{table}.csv")]


def main(tables: list[str]) -> None:
    CACHE.mkdir(exist_ok=True)
    for table in tables:
        files = source_files(table)
        usecols = KEEP.get(table)
        frames = [pd.read_csv(f, encoding="utf-8-sig", dtype=str, usecols=usecols) for f in files]
        df = pd.concat(frames, ignore_index=True)
        df.to_parquet(CACHE / f"{table}.parquet", index=False)
        print(f"{table}: {len(files)} files, {len(df)} raw rows, {len(df.columns)} columns")


if __name__ == "__main__":
    main(sys.argv[1:])
