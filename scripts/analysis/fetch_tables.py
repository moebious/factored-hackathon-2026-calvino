"""Download selected tables from the data bucket into the git-ignored data/ folder.

Usage: python scripts/analysis/fetch_tables.py TABLE [TABLE ...]

Reads the bucket name from CALVINO_DATA_BUCKET and the credentials from the standard
AWS environment variables (access key id, secret key, region); nothing is stored in files. Only the
live `data/` prefix is read, never the dated backup. Partitioned tables are
mirrored as data/<table>/year=.../month=.../day=.../*.csv; single-file tables
(customers, products, ...) as data/<table>.csv. Existing files of the same size
are skipped, so reruns are cheap.
"""

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import boto3
from boto3.s3.transfer import TransferConfig

LIVE_PREFIX = "data/"
OUT_DIR = Path(__file__).resolve().parents[2] / "data"


def list_table(s3, bucket: str, table: str) -> list[tuple[str, int]]:
    """Return (key, size) for every object of a table, partitioned or single-file."""
    objects = []
    for prefix in (f"{LIVE_PREFIX}{table}/", f"{LIVE_PREFIX}{table}.csv"):
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
            objects += [(o["Key"], o["Size"]) for o in page.get("Contents", [])]
    return objects


def main(tables: list[str]) -> None:
    bucket = os.environ["CALVINO_DATA_BUCKET"]
    s3 = boto3.client("s3")
    cfg = TransferConfig(max_concurrency=4)

    def fetch(item: tuple[str, int]) -> int:
        key, size = item
        dest = OUT_DIR / key.removeprefix(LIVE_PREFIX)
        if dest.exists() and dest.stat().st_size == size:
            return 0
        dest.parent.mkdir(parents=True, exist_ok=True)
        s3.download_file(bucket, key, str(dest), Config=cfg)
        return size

    for table in tables:
        items = list_table(s3, bucket, table)
        with ThreadPoolExecutor(8) as pool:
            fetched = sum(pool.map(fetch, items))
        print(f"{table}: {len(items)} files, {fetched / 1e6:.1f} MB downloaded")


if __name__ == "__main__":
    main(sys.argv[1:])
