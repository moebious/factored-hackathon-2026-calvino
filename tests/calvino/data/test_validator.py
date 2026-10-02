"""Table-level audit (TSD-007) on the synthetic lakehouse fixture and broken variants of it."""

from __future__ import annotations

import shutil
from pathlib import Path

import duckdb
import pytest

from calvino.data import audit

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "lakehouse"


def _copy(tmp_path: Path) -> Path:
    target = tmp_path / "lake"
    shutil.copytree(FIXTURE, target)
    return target


def _append(path: Path, line: str) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _checks(report, table):
    t = next(t for t in report.tables if t.table == table)
    return {c.check_id: c for c in t.checks}, t


def test_fixture_passes_with_every_known_defect_counted():
    report = audit(FIXTURE)
    assert report.passed
    assert report.absent == []
    expected = {
        ("transactions", "TX-RESPONSE-CODE-NULL"): 2,
        ("transactions", "TX-COUNTRY-MEXICO"): 1,
        ("complaints", "CP-AMOUNT-NO-CURRENCY"): 1,
        ("complaints", "CP-ORIGIN-NULL"): 3,
        ("call_center_interactions", "CI-REASON-REPEATS"): 3,
        ("service_agents", "FK-assigned_branch_id"): 1,
    }
    for (table, check_id), count in expected.items():
        checks, _ = _checks(report, table)
        assert checks[check_id].violations == count, (table, check_id)
        assert not checks[check_id].failed


def test_parquet_gives_the_same_report_as_csv(tmp_path):
    out = tmp_path / "parquet"
    out.mkdir()
    con = duckdb.connect()
    for csv in FIXTURE.glob("*.csv"):
        con.execute(
            f"COPY (SELECT * FROM read_csv('{csv}', header = true)) "
            f"TO '{out / (csv.stem + '.parquet')}' (FORMAT parquet)"
        )
    con.close()
    as_csv = {(t.table, c.check_id): c.violations for t in audit(FIXTURE).tables for c in t.checks}
    as_parquet = {(t.table, c.check_id): c.violations for t in audit(out).tables for c in t.checks}
    assert as_parquet == as_csv


def test_partitioned_parquet_folder_is_read(tmp_path):
    folder = tmp_path / "lake" / "customers" / "year=2023"
    folder.mkdir(parents=True)
    con = duckdb.connect()
    con.execute(
        f"COPY (SELECT * FROM read_csv('{FIXTURE / 'customers.csv'}', header = true)) "
        f"TO '{folder / 'part-0.parquet'}' (FORMAT parquet)"
    )
    con.close()
    report = audit(tmp_path / "lake")
    assert [t.table for t in report.tables] == ["customers"]
    assert report.tables[0].rows == 3


def test_partitioned_csv_folder_is_read(tmp_path):
    for day, rows in (("17", "C001,México,Basic,mexicano,640"), ("18", "C002,Colombia,,,")):
        folder = tmp_path / "raw" / "customers" / "year=2023" / "month=06" / f"day={day}"
        folder.mkdir(parents=True)
        (folder / "part.csv").write_text(
            "customer_id,country,segment,detected_accent,credit_score\n" + rows + "\n",
            encoding="utf-8",
        )
    report = audit(tmp_path / "raw")
    assert report.tables[0].rows == 2
    assert report.passed


def test_duplicate_primary_key_fails(tmp_path):
    lake = _copy(tmp_path)
    _append(lake / "customers.csv", "C001,México,Basic,mexicano,640")
    report = audit(lake)
    checks, _ = _checks(report, "customers")
    assert checks["PK-DUPLICATE"].violations == 1
    assert not report.passed


def test_orphan_customer_fails(tmp_path):
    lake = _copy(tmp_path)
    _append(
        lake / "transactions.csv",
        "T099,C999,P001,2023-06-21 10:00:00,Transfer,Pending,10.00,MXN,0.58,00,México,false,App",
    )
    report = audit(lake)
    checks, _ = _checks(report, "transactions")
    assert checks["FK-customer_id"].violations == 1
    assert checks["FK-customer_id"].failed
    assert not report.passed


@pytest.mark.parametrize(
    ("table", "line", "check_id"),
    [
        (
            "transactions",
            "T098,C001,P001,2023-06-21 10:00:00,Transfer,Pending,10.00,BRL,2.00,00,"
            "México,false,App",
            "TX-CURRENCY",
        ),
        ("customers", "C004,Brasil,Basic,,600", "CU-COUNTRY"),
        ("daily_exchange_rates", "2023-06-18,MXN,USD,0", "FX-RATE-POSITIVE"),
    ],
)
def test_rule_errors_fail_the_audit(tmp_path, table, line, check_id):
    lake = _copy(tmp_path)
    _append(lake / f"{table}.csv", line)
    report = audit(lake)
    checks, _ = _checks(report, table)
    assert checks[check_id].violations == 1
    assert not report.passed


def test_missing_required_column_fails(tmp_path):
    lake = _copy(tmp_path)
    (lake / "branches.csv").write_text("id\nB01\n", encoding="utf-8")
    report = audit(lake)
    _, branches = _checks(report, "branches")
    assert branches.missing_columns == ["branch_id"]
    assert not report.passed


def test_absent_table_is_listed_and_its_foreign_keys_skipped(tmp_path):
    lake = _copy(tmp_path)
    (lake / "branches.csv").unlink()
    report = audit(lake)
    assert "branches" in report.absent
    _, agents = _checks(report, "service_agents")
    assert any("branches absent" in s for s in agents.skipped)
    assert report.passed


def test_report_serialises():
    data = audit(FIXTURE).to_dict()
    assert data["passed"] is True
    assert {"table", "rows", "checks", "passed"} <= set(data["tables"][0])


def test_not_a_directory_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        audit(tmp_path / "missing")
