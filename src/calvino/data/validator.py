"""Contract validator (TSD-007): row-level checks for samples, table-level audit for files.

``validate_records`` runs the Pydantic row models over a list of rows: for fixtures and
small samples. ``audit`` runs every table-level check as a DuckDB aggregate query over the
Parquet or CSV files in a directory, so the full data (millions of rows) never passes
through Python row by row. Checks with severity ``known_defect`` are counted and reported
but never fail the audit.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import duckdb
from pydantic import ValidationError

from calvino.data.contracts import TABLES, Severity, TableContract, rules_for


@dataclass(frozen=True)
class CheckResult:
    """One check on one table: how many rows violate it, and whether that fails the audit."""

    check_id: str
    severity: Severity
    violations: int
    meaning: str

    @property
    def failed(self) -> bool:
        return self.severity is Severity.ERROR and self.violations > 0


@dataclass
class TableReport:
    """Every check on one table, plus the columns the contract needs but the file lacks."""

    table: str
    source: str
    rows: int
    missing_columns: list[str] = field(default_factory=list)
    checks: list[CheckResult] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.missing_columns and not any(c.failed for c in self.checks)


@dataclass
class AuditReport:
    """The audit of one directory. ``passed`` is false only when an error check fails."""

    directory: str
    tables: list[TableReport] = field(default_factory=list)
    absent: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(t.passed for t in self.tables)

    def to_dict(self) -> dict[str, Any]:
        return {
            "directory": self.directory,
            "passed": self.passed,
            "absent_tables": self.absent,
            "tables": [
                {
                    **{k: v for k, v in asdict(t).items() if k != "checks"},
                    "passed": t.passed,
                    "checks": [{**asdict(c), "failed": c.failed} for c in t.checks],
                }
                for t in self.tables
            ],
        }


@dataclass
class RowValidation:
    """Row-level result: valid and invalid counts, and errors grouped by field and message."""

    table: str
    valid: int = 0
    invalid: int = 0
    errors: Counter[str] = field(default_factory=Counter)


def validate_records(table: str, rows: Iterable[Mapping[str, Any]]) -> RowValidation:
    """Validate rows against the table's row model (fixtures and samples only)."""
    contract = TABLES[table]
    result = RowValidation(table)
    for row in rows:
        try:
            contract.model.model_validate(dict(row))
            result.valid += 1
        except ValidationError as err:
            result.invalid += 1
            for e in err.errors():
                where = ".".join(str(p) for p in e["loc"]) or "row"
                result.errors[f"{where}: {e['msg']}"] += 1
    return result


def _find_source(directory: Path, table: str) -> Path | None:
    """A table is ``<table>.parquet``, ``<table>.csv``, or a ``<table>/`` folder of Parquet or
    CSV files (the organizer's partitioned layout, ``year=/month=/day=``)."""
    for candidate in (directory / f"{table}.parquet", directory / f"{table}.csv"):
        if candidate.is_file():
            return candidate
    folder = directory / table
    if folder.is_dir() and (any(folder.rglob("*.parquet")) or any(folder.rglob("*.csv"))):
        return folder
    return None


def _quote(path: Path | str) -> str:
    return "'" + str(path).replace("'", "''") + "'"


def _reader(source: Path) -> str:
    if source.is_dir():
        if any(source.rglob("*.parquet")):
            return f"read_parquet({_quote(source / '**' / '*.parquet')}, union_by_name = true)"
        return f"read_csv({_quote(source / '**' / '*.csv')}, header = true, union_by_name = true)"
    if source.suffix == ".parquet":
        return f"read_parquet({_quote(source)})"
    return f"read_csv({_quote(source)}, header = true)"


def _count(con: duckdb.DuckDBPyConnection, sql: str) -> int:
    row = con.execute(sql).fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def _audit_table(
    con: duckdb.DuckDBPyConnection,
    contract: TableContract,
    source: Path,
    loaded: dict[str, set[str]],
) -> TableReport:
    t = contract.name
    columns = loaded[t]
    report = TableReport(t, str(source), _count(con, f"SELECT COUNT(*) FROM {t}"))
    report.missing_columns = [c for c in contract.required if c not in columns]
    if report.missing_columns:
        return report

    pk = ", ".join(contract.primary_key)
    pk_null = " OR ".join(f"{c} IS NULL" for c in contract.primary_key)
    report.checks.append(
        CheckResult(
            "PK-NULL",
            Severity.ERROR,
            _count(con, f"SELECT COUNT(*) FROM {t} WHERE {pk_null}"),
            f"primary key ({pk}) is present",
        )
    )
    report.checks.append(
        CheckResult(
            "PK-DUPLICATE",
            Severity.ERROR,
            _count(
                con,
                f"SELECT COALESCE(SUM(n - 1), 0) FROM "
                f"(SELECT COUNT(*) AS n FROM {t} WHERE NOT ({pk_null}) GROUP BY {pk})",
            ),
            f"primary key ({pk}) is unique",
        )
    )
    for col in contract.required:
        if col in contract.primary_key:
            continue
        report.checks.append(
            CheckResult(
                f"REQUIRED-{col}",
                Severity.ERROR,
                _count(con, f"SELECT COUNT(*) FROM {t} WHERE {col} IS NULL"),
                f"{col} is present",
            )
        )
    for fk in contract.foreign_keys:
        if fk.column not in columns:
            report.skipped.append(f"FK {fk.column}: column absent")
            continue
        if fk.parent not in loaded:
            report.skipped.append(f"FK {fk.column}: parent table {fk.parent} absent")
            continue
        if fk.parent_column not in loaded[fk.parent]:
            report.skipped.append(f"FK {fk.column}: {fk.parent}.{fk.parent_column} absent")
            continue
        orphans = _count(
            con,
            f"SELECT COUNT(*) FROM {t} c WHERE c.{fk.column} IS NOT NULL AND NOT EXISTS "
            f"(SELECT 1 FROM {fk.parent} p WHERE p.{fk.parent_column} = c.{fk.column})",
        )
        report.checks.append(
            CheckResult(
                f"FK-{fk.column}",
                fk.severity,
                orphans,
                f"{fk.column} exists in {fk.parent}.{fk.parent_column}",
            )
        )
    for rule in rules_for(t):
        # A rule over an absent optional column (or one of another type) is skipped and
        # listed, never silently passed.
        try:
            violations = _count(con, f"SELECT COUNT(*) FROM {t} WHERE {rule.predicate}")
        except duckdb.BinderException as err:
            report.skipped.append(f"{rule.rule_id}: {str(err).splitlines()[0]}")
            continue
        report.checks.append(CheckResult(rule.rule_id, rule.severity, violations, rule.meaning))
    return report


def audit(directory: Path | str) -> AuditReport:
    """Run every contract check over the tables found in ``directory``."""
    root = Path(directory)
    if not root.is_dir():
        raise FileNotFoundError(f"not a directory: {root}")
    report = AuditReport(str(root))
    con = duckdb.connect()
    try:
        sources: dict[str, Path] = {}
        for name in TABLES:
            source = _find_source(root, name)
            if source is None:
                report.absent.append(name)
                continue
            con.execute(f"CREATE VIEW {name} AS SELECT * FROM {_reader(source)}")
            sources[name] = source
        # Columns per loaded table, so foreign keys into a malformed parent are skipped.
        loaded = {
            name: {r[0] for r in con.execute(f"DESCRIBE {name}").fetchall()} for name in sources
        }
        for name, source in sources.items():
            report.tables.append(_audit_table(con, TABLES[name], source, loaded))
    finally:
        con.close()
    return report
