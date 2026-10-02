"""Audit a folder of tables against the data contracts (TSD-007).

``uv run python scripts/validate_data_contracts.py --dir tests/fixtures/lakehouse``
``uv run python scripts/validate_data_contracts.py --dir data/lakehouse --output report.json``

Tables are ``<table>.parquet``, ``<table>.csv`` or a ``<table>/`` folder of Parquet files.
Prints one line per check that found violations; exits 1 when an error check fails. Known
defects are listed but never change the exit code. Write reports with real counts under
``reports/`` only as aggregates.
"""

import argparse
import json
import sys
from pathlib import Path

from calvino.data import audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", required=True, type=Path, help="folder holding the tables")
    parser.add_argument("--output", type=Path, help="write the full report as JSON here")
    args = parser.parse_args()

    report = audit(args.dir)
    for table in report.tables:
        status = "ok" if table.passed else "FAILED"
        print(f"{table.table}: {table.rows:,} rows, {status}")
        if table.missing_columns:
            print(f"  missing required columns: {', '.join(table.missing_columns)}")
        for check in table.checks:
            if check.violations:
                kind = "ERROR" if check.failed else check.severity.value
                print(f"  {check.check_id}: {check.violations:,} ({kind}) {check.meaning}")
        for note in table.skipped:
            print(f"  skipped {note}")
    if report.absent:
        print(f"absent tables: {', '.join(report.absent)}")
    if args.output:
        args.output.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
    print("PASSED" if report.passed else "FAILED")
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
