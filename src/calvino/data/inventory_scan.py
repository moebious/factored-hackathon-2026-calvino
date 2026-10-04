"""Bounded-memory CSV inventory: all rows, safe aggregates, no retained record values."""

from __future__ import annotations

import csv
import io
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import BinaryIO

from botocore.exceptions import BotoCoreError, ClientError

from calvino.data.contracts import TABLES
from calvino.data.inventory_access import InventoryError, SourceObject, _safe_error

# Only known, low-cardinality values can appear in a public distribution. New
# values are counted as "other", never echoed from an organizer record.
SAFE_CATEGORIES: dict[str, dict[str, frozenset[str]]] = {
    "customers": {
        "country": frozenset({"México", "Colombia", "Argentina"}),
        "segment": frozenset({"Premium", "Plus", "Basic", "Student"}),
    },
    "transactions": {
        "transaction_status": frozenset({"Approved", "Declined", "Pending", "Reversed"}),
        "transaction_type": frozenset(
            {"Deposit", "Withdrawal", "Transfer", "Payment", "Purchase", "Adjustment"}
        ),
        "currency": frozenset({"MXN", "COP", "ARS", "USD"}),
    },
    "call_center_interactions": {
        "reason_category": frozenset(
            {"Comercial", "Producto", "Queja", "Retención", "Transaccional", "Técnico"}
        ),
    },
    "complaints": {
        "category": frozenset({"Transactions"}),
        "status": frozenset({"Open", "In Process", "Escalated", "Rejected", "Resolved", "Closed"}),
        "currency": frozenset({"MXN", "COP", "ARS", "USD"}),
    },
}
_INTEGER = re.compile(r"^-?\d+$")
_DECIMAL = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[ T].*)?$")
_COLUMN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,99}$")
_CURRENCIES = frozenset({"MXN", "COP", "ARS", "USD"})
_COUNTRIES = frozenset({"México", "Colombia", "Argentina"})
_STATUSES = frozenset({"Approved", "Declined", "Pending", "Reversed"})
_RULE_FIELDS: dict[str, frozenset[str]] = {
    "products": frozenset({"currency"}),
    "transactions": frozenset({"currency", "response_code", "transaction_country"}),
    "complaints": frozenset({"claimed_amount", "currency", "origin_interaction_id"}),
    "call_center_interactions": frozenset({"contact_reason"}),
    "service_agents": frozenset({"assigned_branch_id"}),
}


def _kind(value: str) -> str:
    if value in ("True", "False", "true", "false"):
        return "boolean"
    if _INTEGER.fullmatch(value):
        return "integer"
    if _DECIMAL.fullmatch(value):
        return "decimal"
    if _DATE.fullmatch(value):
        return "date_or_timestamp"
    return "text"


def _families(types: set[str]) -> set[str]:
    """Integer and decimal (including scientific notation) are one numeric family."""
    return {"number" if kind in {"integer", "decimal"} else kind for kind in types}


@dataclass
class ColumnCounts:
    """Null/empty and coarse type counts, never examples."""

    missing: int = 0
    empty: int = 0
    types: Counter[str] = field(default_factory=Counter)

    def result(self, rows: int) -> dict[str, object]:
        return {
            "missing": self.missing,
            "empty": self.empty,
            "null_or_empty": self.missing + self.empty,
            "null_or_empty_rate": (self.missing + self.empty) / rows if rows else None,
            "types": dict(sorted(self.types.items())),
        }


@dataclass
class TableCounts:
    """One table's streaming aggregates and per-file schema checks."""

    name: str
    rows: int = 0
    files: int = 0
    headers: set[str] = field(default_factory=set)
    columns: dict[str, ColumnCounts] = field(default_factory=dict)
    drift: Counter[str] = field(default_factory=Counter)
    categories: dict[str, Counter[str]] = field(default_factory=dict)
    row_rules: Counter[str] = field(default_factory=Counter)
    first_file_types: dict[str, set[str]] = field(default_factory=dict)

    def result(self) -> dict[str, object]:
        return {
            "rows": self.rows,
            "files": self.files,
            "columns": {k: v.result(self.rows) for k, v in sorted(self.columns.items())},
            "schema_drift": dict(sorted(self.drift.items())),
            "row_rule_violations": dict(sorted(self.row_rules.items())),
            "categories": {
                col: {
                    "counts": dict(sorted(values.items())),
                    "denominator": self.rows,
                    "small_n": sorted(k for k, n in values.items() if 0 < n < 30),
                }
                for col, values in sorted(self.categories.items())
            },
        }


def scan_table(
    name: str,
    objects: list[SourceObject],
    open_object: Callable[[SourceObject], BinaryIO],
    on_row: Callable[[TableCounts, dict[str, str | None]], None] | None = None,
) -> TableCounts:
    """Stream every record once, discarding row values immediately after counting."""
    table = TableCounts(name)
    safe = SAFE_CATEGORIES.get(name, {})
    table.categories = {column: Counter() for column in safe}
    if not objects:
        raise InventoryError(f"live table {name} has no source objects")
    for obj in objects:
        if obj.table != name:
            raise InventoryError("object belongs to the wrong table")
        try:
            body = open_object(obj)
            with io.TextIOWrapper(body, encoding="utf-8-sig", newline="") as text:
                reader = csv.DictReader(text)
                header = reader.fieldnames
                if (
                    not header
                    or len(header) != len(set(header))
                    or any(not _COLUMN.fullmatch(col) for col in header)
                ):
                    raise InventoryError(f"live table {name} has an invalid CSV header")
                observed = set(header)
                required = (
                    set(TABLES[name].required) | _RULE_FIELDS.get(name, frozenset())
                    if name in TABLES
                    else set()
                )
                if required - observed:
                    raise InventoryError(f"live table {name} is missing required inventory columns")
                if table.files == 0:
                    table.headers = observed
                else:
                    if table.headers - observed:
                        table.drift["files_with_missing_columns"] += 1
                    if observed - table.headers:
                        table.drift["files_with_extra_columns"] += 1
                first_file = table.files == 0
                table.files += 1
                file_types: dict[str, set[str]] = {column: set() for column in observed}
                for column in observed - table.columns.keys():
                    table.columns[column] = ColumnCounts(missing=table.rows)
                for row in reader:
                    if None in row:
                        raise InventoryError(f"live table {name} has an unexpected CSV field")
                    table.rows += 1
                    for column, counts in table.columns.items():
                        value = row.get(column)
                        if value is None:
                            counts.missing += 1
                        elif value == "":
                            counts.empty += 1
                        else:
                            kind = _kind(value)
                            counts.types[kind] += 1
                            file_types[column].add(kind)
                    for column, allowed in safe.items():
                        value = row.get(column)
                        label = value if value in allowed else "(null)" if not value else "(other)"
                        table.categories[column][label] += 1
                    _count_row_rules(table, row)
                    if on_row is not None:
                        on_row(table, row)
                if first_file:
                    table.first_file_types = file_types
                elif any(
                    _families(file_types[column]).isdisjoint(
                        _families(table.first_file_types[column])
                    )
                    for column in observed & table.headers
                    if file_types[column] and table.first_file_types.get(column)
                ):
                    table.drift["files_with_incompatible_type_families"] += 1
                for column, types in file_types.items():
                    if types and not table.first_file_types.get(column):
                        table.first_file_types[column] = types
        except InventoryError:
            raise
        except (ClientError, BotoCoreError) as error:
            raise _safe_error(error) from None
        except (OSError, UnicodeError, csv.Error, ValueError):
            raise InventoryError(f"could not read live table {name}") from None
    return table


def _count_row_rules(table: TableCounts, row: dict[str, str | None]) -> None:
    """Recompute row-local TSD-007 rule counts; PKs and FKs need a separate audit."""
    t = table.name
    rules = table.row_rules
    if t == "transactions":
        rules["TX-STATUS"] += row.get("transaction_status") not in _STATUSES
        rules["TX-CURRENCY"] += row.get("currency") not in _CURRENCIES
        rules["TX-RESPONSE-CODE-NULL"] += not row.get("response_code")
        rules["TX-COUNTRY-MEXICO"] += row.get("transaction_country") == "Mexico"
    elif t == "customers":
        rules["CU-COUNTRY"] += row.get("country") not in _COUNTRIES
    elif t == "products":
        rules["PR-CURRENCY"] += bool(row.get("currency")) and row.get("currency") not in _CURRENCIES
    elif t == "complaints":
        rules["CP-AMOUNT-NO-CURRENCY"] += bool(row.get("claimed_amount")) and not row.get(
            "currency"
        )
        rules["CP-ORIGIN-NULL"] += not row.get("origin_interaction_id")
    elif t == "call_center_interactions":
        rules["CI-REASON-REPEATS"] += (
            bool(row.get("contact_reason"))
            and bool(row.get("reason_category"))
            and row["contact_reason"] == row["reason_category"]
        )
    elif t == "daily_exchange_rates":
        try:
            rate = Decimal(row.get("exchange_rate") or "")
            invalid = not rate.is_finite() or rate <= 0
        except InvalidOperation:
            invalid = True
        rules["FX-RATE-POSITIVE"] += invalid
