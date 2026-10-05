"""Read-only DuckDB adapter for the T-206 cleaned customer, product, and transaction tables."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING, Any

import duckdb
from pydantic import TypeAdapter, ValidationError

from calvino.tools.contracts import (
    Account,
    AccountEntry,
    Amount,
    CancellationOutcome,
    CancellationResponse,
    CountryCode,
    CustomerSummary,
    EntryRecord,
    Investigation,
    InvestigationStatus,
    PaymentStatus,
    RetryResult,
    TransactionStatus,
)
from calvino.tools.errors import ConfigurationError, Rule, ToolRefusal
from calvino.tools.session import Session

_REQUIRED_TABLES = ("customers", "products", "transactions")
_CURRENCY_CODES = frozenset({"MXN", "COP", "ARS", "USD"})
_COUNTRY_CODES = {
    "MX": "MX",
    "Mexico": "MX",
    "México": "MX",
    "CO": "CO",
    "Colombia": "CO",
    "AR": "AR",
    "Argentina": "AR",
    "US": "US",
    "USA": "US",
    "BR": "BR",
    "Brazil": "BR",
    "ES": "ES",
    "Spain": "ES",
}
_AMOUNT_ADAPTER = TypeAdapter(Amount)

if TYPE_CHECKING:
    from calvino.data.validator import AuditReport


class CleanedTableAdapter:
    """Serve the existing ``BankAdapter`` protocol from audited Parquet/CSV tables.

    Queries are parameterized and owner-filtered. All write methods only append
    to this instance's action log and case store; they never write source files.
    """

    def __init__(
        self,
        cleaned_root: Path,
        *,
        lineage_path: Path,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        # Import lazily: ``calvino.data.__init__`` imports the oracle, which
        # imports the hub and tools. A module-level import would cycle while
        # ``calvino.tools`` exposes this adapter.
        from calvino.data.validator import audit

        self._root = Path(cleaned_root)
        self._clock = clock or (lambda: datetime.now(UTC))
        self.action_log: list[dict[str, str]] = []
        self._cases: dict[str, tuple[str, Investigation]] = {}
        self._lock = threading.RLock()
        self._columns: dict[str, set[str]] = {}
        self._connection = duckdb.connect(database=":memory:")

        try:
            report = audit(self._root)
            self._require_valid_tables(report)
            self._create_views()
            self._columns = {
                table: {
                    str(row[0]) for row in self._connection.execute(f"DESCRIBE {table}").fetchall()
                }
                for table in _REQUIRED_TABLES
            }
            self._incomplete_source_counts = self._count_incomplete_source_fields()
            if self._incomplete_source_counts["transactions.fraud_flag_invalid"]:
                raise ConfigurationError("the cleaned fraud flags contain invalid values")
            owner_mismatches = self._customer_product_integrity_count()
            if owner_mismatches:
                raise ConfigurationError(
                    "the cleaned transaction/product ownership audit failed: "
                    f"{owner_mismatches} mismatches"
                )
            self._write_lineage(Path(lineage_path), report, owner_mismatches)
        except Exception:
            self._connection.close()
            raise

    def close(self) -> None:
        """Release the in-memory DuckDB connection."""
        with self._lock:
            self._connection.close()

    def get_customer_summary(self, session: Session) -> CustomerSummary:
        columns = ["customer_id", "country"]
        if "segment" in self._columns["customers"]:
            columns.append("segment")
        rows = self._query(
            f"SELECT {', '.join(columns)} FROM customers WHERE customer_id = ? LIMIT 1",
            [session.customer_id],
        )
        if not rows:
            raise ToolRefusal(Rule.NOT_FOUND, "no customer for this session")
        customer = rows[0]
        return CustomerSummary(
            customer_id=str(customer["customer_id"]),
            display_name=None,
            country=self._customer_country(customer["country"]),
            segment=_optional_text(customer.get("segment")),
            account_count=None,
        )

    def list_accounts(self, session: Session) -> list[Account]:
        columns = ["product_id"]
        columns.extend(
            field for field in ("product_type", "currency") if field in self._columns["products"]
        )
        rows = self._query(
            f"SELECT {', '.join(columns)} FROM products WHERE customer_id = ? ORDER BY product_id",
            [session.customer_id],
        )
        return [
            Account(
                account_id=str(row["product_id"]),
                account_type=_optional_text(row["product_type"]),
                currency=self._currency(row.get("currency")),
                status=None,
                balance=None,
            )
            for row in rows
        ]

    def get_account_entries(
        self,
        session: Session,
        account_id: str,
        date_from: date | None,
        date_to: date | None,
    ) -> list[AccountEntry]:
        if "product_id" not in self._columns["products"]:
            raise ToolRefusal(Rule.NOT_FOUND, "no source product identifiers are available")
        product = self._query(
            "SELECT customer_id FROM products WHERE product_id = ? LIMIT 1",
            [account_id],
        )
        if not product:
            raise ToolRefusal(Rule.NOT_FOUND, "no such account")
        if str(product[0]["customer_id"]) != session.customer_id:
            raise ToolRefusal(
                Rule.NOT_OWNER, "the account does not belong to this session's customer"
            )
        if "product_id" not in self._columns["transactions"]:
            return []
        return [
            self._entry(row)
            for row in self._transaction_rows(
                "product_id = ? AND customer_id = ?",
                [account_id, session.customer_id],
                date_from,
                date_to,
            )
        ]

    def get_entry_detail(self, session: Session, entry_reference: str) -> AccountEntry:
        return self.get_entry_record(session, entry_reference).entry

    def get_entry_record(self, session: Session, entry_reference: str) -> EntryRecord:
        rows = self._query(
            """
            SELECT * FROM transactions
            WHERE transaction_id = ? AND customer_id = ?
            LIMIT 1
            """,
            [entry_reference, session.customer_id],
        )
        if not rows:
            owners = self._query(
                "SELECT customer_id FROM transactions WHERE transaction_id = ? LIMIT 1",
                [entry_reference],
            )
            if owners:
                raise ToolRefusal(
                    Rule.NOT_OWNER, "the entry does not belong to this session's customer"
                )
            raise ToolRefusal(Rule.NOT_FOUND, "no such entry")
        row = rows[0]
        fraud_flagged = _source_bool(row.get("is_fraud"))
        return EntryRecord(
            entry=self._entry(row),
            customer_id=str(row["customer_id"]),
            account_id=_optional_text(row.get("product_id")),
            transaction_type=_optional_text(row.get("transaction_type")),
            fraud_flagged=fraud_flagged if type(fraud_flagged) is bool else None,
            status_reason=None,
            response_code=_optional_text(row.get("response_code")),
        )

    def get_payment_status(self, session: Session, entry_reference: str) -> PaymentStatus:
        record = self.get_entry_record(session, entry_reference)
        return PaymentStatus(
            original_reference=entry_reference,
            status=record.entry.status,
            reason=record.status_reason,
        )

    def list_problem_transactions(
        self, session: Session, date_from: date | None, date_to: date | None
    ) -> list[AccountEntry]:
        return [
            self._entry(row)
            for row in self._transaction_rows(
                "customer_id = ? AND transaction_status IN (?, ?, ?)",
                [
                    session.customer_id,
                    TransactionStatus.DECLINED.value,
                    TransactionStatus.PENDING.value,
                    TransactionStatus.REVERSED.value,
                ],
                date_from,
                date_to,
            )
        ]

    def cancel_payment(
        self, session: Session, entry_reference: str, reason: str, idempotency_key: str
    ) -> CancellationResponse:
        self.get_entry_record(session, entry_reference)
        self.action_log.append(
            {
                "action": "cancel_payment",
                "customer_id": session.customer_id,
                "target": entry_reference,
            }
        )
        return CancellationResponse(
            original_reference=entry_reference,
            reason=reason,
            requested_by=session.customer_id,
            outcome=CancellationOutcome.ACCEPTED,
            simulated=True,
            message="SIMULATED: the cancellation was recorded in the adapter's action log only; "
            "no real payment was changed.",
        )

    def retry_payment(
        self, session: Session, entry_reference: str, idempotency_key: str
    ) -> RetryResult:
        self.get_entry_record(session, entry_reference)
        new_reference = _retry_reference(session.customer_id, idempotency_key)
        self.action_log.append(
            {
                "action": "retry_payment",
                "customer_id": session.customer_id,
                "target": entry_reference,
                "new_reference": new_reference,
            }
        )
        return RetryResult(
            original_reference=entry_reference,
            new_payment=PaymentStatus(
                original_reference=new_reference,
                status=TransactionStatus.PENDING,
            ),
            simulated=True,
            message="SIMULATED: the retry was recorded in the adapter's action log only; "
            "no real payment was created.",
        )

    def open_investigation(
        self, session: Session, entry_reference: str, reason: str, idempotency_key: str
    ) -> Investigation:
        self.get_entry_record(session, entry_reference)
        case_id = f"CASE-{_retry_reference(session.customer_id, idempotency_key)}"
        case = Investigation(
            case_id=case_id,
            related_entry_reference=entry_reference,
            reason=reason,
            status=InvestigationStatus.OPEN,
            opened_at=self._clock(),
            next_step="A person will review the full file and contact you.",
        )
        self._cases[case_id] = (session.customer_id, case)
        self.action_log.append(
            {"action": "open_investigation", "customer_id": session.customer_id, "target": case_id}
        )
        return case

    def get_investigation_status(self, session: Session, case_id: str) -> Investigation:
        found = self._cases.get(case_id)
        if found is None:
            raise ToolRefusal(Rule.NOT_FOUND, "no such case")
        owner, case = found
        if owner != session.customer_id:
            raise ToolRefusal(Rule.NOT_OWNER, "the case does not belong to this session's customer")
        return case

    def _require_valid_tables(self, report: Any) -> None:
        by_name = {table.table: table for table in report.tables}
        missing = sorted(set(_REQUIRED_TABLES) - by_name.keys())
        if missing or any(not by_name[name].passed for name in _REQUIRED_TABLES if name in by_name):
            raise ConfigurationError(
                "the cleaned customer/product/transaction tables failed TSD-007"
            )

    def _create_views(self) -> None:
        for table in _REQUIRED_TABLES:
            source = _find_source(self._root, table)
            if source is None:
                raise ConfigurationError("a required cleaned table is absent")
            if source.is_dir():
                files = sorted(source.rglob("*.parquet"))
                extension = "parquet" if files else "csv"
                pattern = "**/*.parquet" if files else "**/*.csv"
                source_sql = (
                    f"read_parquet({_sql_string(source / pattern)}, union_by_name = true)"
                    if extension == "parquet"
                    else (
                        f"read_csv({_sql_string(source / pattern)}, "
                        "header = true, union_by_name = true)"
                    )
                )
            elif source.suffix.lower() == ".parquet":
                source_sql = f"read_parquet({_sql_string(source)})"
            else:
                source_sql = f"read_csv({_sql_string(source)}, header = true)"
            self._connection.execute(f"CREATE VIEW {table} AS SELECT * FROM {source_sql}")

    def _customer_product_integrity_count(self) -> int:
        if "product_id" not in self._columns["transactions"]:
            return 0
        row = self._connection.execute(
            """
            SELECT COUNT(*)
            FROM transactions AS tx
            LEFT JOIN products AS p ON p.product_id = tx.product_id
            WHERE tx.product_id IS NOT NULL
              AND (p.product_id IS NULL OR tx.customer_id <> p.customer_id)
            """
        ).fetchone()
        return int(row[0]) if row and row[0] is not None else 0

    def _count_incomplete_source_fields(self) -> dict[str, int]:
        fields = {
            "customers": (
                ("customers.display_name", None),
                ("customers.account_count", None),
            ),
            "products": (
                ("products.product_type", "product_type"),
                ("products.currency", "currency"),
                ("products.status", None),
                ("products.balance", None),
            ),
            "transactions": (
                ("transactions.product_id", "product_id"),
                ("transactions.transaction_date", "transaction_date"),
                ("transactions.transaction_type", "transaction_type"),
                ("transactions.amount", "amount"),
                ("transactions.currency", "currency"),
                ("transactions.is_fraud", "is_fraud"),
                ("transactions.transaction_country", "transaction_country"),
                ("transactions.value_date", None),
                ("transactions.status_reason", None),
                ("transactions.credit_debit", None),
                ("transactions.bank_transaction_code", None),
                ("transactions.remittance_information", None),
                ("transactions.merchant_category_code", None),
            ),
        }
        result: dict[str, int] = {}
        for table, table_fields in fields.items():
            columns = self._columns[table]
            expressions = []
            keys = []
            for key, column in table_fields:
                expression = (
                    f"COUNT(*) FILTER (WHERE {column} IS NULL)"
                    if column is not None and column in columns
                    else "COUNT(*)"
                )
                expressions.append(expression)
                keys.append(key)
            if table == "transactions":
                expressions.append(
                    """
                    COUNT(*) FILTER (
                        WHERE amount IS NOT NULL
                          AND (
                            TRY_CAST(amount AS DECIMAL(18, 2)) IS NULL
                            OR TRY_CAST(amount AS DECIMAL(18, 2)) <= 0
                            OR NOT regexp_full_match(
                                CAST(amount AS VARCHAR), '[0-9]{1,16}([.][0-9]{1,2})?'
                            )
                          )
                    )
                    """
                    if "amount" in columns
                    else "0"
                )
                keys.append("transactions.amount_not_representable")
                expressions.append(
                    """
                    COUNT(*) FILTER (
                        WHERE transaction_country IS NOT NULL
                          AND transaction_country NOT IN (
                            'MX', 'Mexico', 'México', 'CO', 'Colombia', 'AR', 'Argentina',
                            'US', 'USA', 'BR', 'Brazil', 'ES', 'Spain'
                          )
                    )
                    """
                    if "transaction_country" in columns
                    else "0"
                )
                keys.append("transactions.transaction_country_unmapped")
                expressions.append(
                    """
                    COUNT(*) FILTER (
                        WHERE is_fraud IS NOT NULL
                          AND lower(CAST(is_fraud AS VARCHAR))
                              NOT IN ('true', 'false', '1', '0')
                    )
                    """
                    if "is_fraud" in columns
                    else "0"
                )
                keys.append("transactions.fraud_flag_invalid")
            row = self._connection.execute(
                f"SELECT {', '.join(expressions)} FROM {table}"
            ).fetchone()
            result.update(
                {
                    key: int(value) if value is not None else 0
                    for key, value in zip(keys, row or (), strict=True)
                }
            )
        return result

    def _write_lineage(self, target: Path, report: AuditReport, owner_mismatches: int) -> None:
        root = self._root.resolve()
        resolved_target = target.resolve()
        try:
            resolved_target.relative_to(root)
        except ValueError:
            pass
        else:
            raise ConfigurationError("the cleaned-table lineage output must be outside the source")

        inputs = {}
        for table in _REQUIRED_TABLES:
            source = _find_source(self._root, table)
            if source is None:
                raise ConfigurationError("a required cleaned table is absent")
            inputs[table] = {
                "sha256": _hash_source(self._root, source),
                "file_count": len(_source_files(source)),
                "rows": next(item.rows for item in report.tables if item.table == table),
            }
        target.parent.mkdir(parents=True, exist_ok=True)
        manifest = json.dumps(
            {
                "contract": "TSD-007",
                "passed": report.passed and owner_mismatches == 0,
                "tables": inputs,
                "transaction_product_owner_mismatches": owner_mismatches,
                "incomplete_source_counts": self._incomplete_source_counts,
                "known_defects": {
                    table.table: {
                        check.check_id: check.violations
                        for check in table.checks
                        if check.severity.value == "known_defect"
                    }
                    for table in report.tables
                    if table.table in _REQUIRED_TABLES
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        manifest += "\n"
        if target.exists():
            self._require_identical_lineage(target, manifest)
            return

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temporary_path = Path(stream.name)
                stream.write(manifest)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary_path, target)
            except FileExistsError:
                self._require_identical_lineage(target, manifest)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _require_identical_lineage(target: Path, manifest: str) -> None:
        try:
            existing = target.read_text(encoding="utf-8")
        except OSError as exc:
            raise ConfigurationError(
                "the cleaned-table lineage output exists but cannot be verified"
            ) from exc
        if existing != manifest:
            raise ConfigurationError(
                "the cleaned-table lineage output already exists with different content"
            )

    def _transaction_rows(
        self,
        predicate: str,
        parameters: list[Any],
        date_from: date | None,
        date_to: date | None,
    ) -> list[dict[str, Any]]:
        conditions = [predicate]
        values = list(parameters)
        if (date_from is not None or date_to is not None) and (
            "transaction_date" not in self._columns["transactions"]
        ):
            return []
        if date_from is not None:
            conditions.append(
                "transaction_date IS NOT NULL AND CAST(transaction_date AS DATE) >= ?"
            )
            values.append(date_from)
        if date_to is not None:
            conditions.append(
                "transaction_date IS NOT NULL AND CAST(transaction_date AS DATE) <= ?"
            )
            values.append(date_to)
        return self._query(
            "SELECT * FROM transactions WHERE "
            + " AND ".join(f"({condition})" for condition in conditions)
            + " ORDER BY transaction_id",
            values,
        )

    def _query(self, sql: str, parameters: Sequence[Any]) -> list[dict[str, Any]]:
        with self._lock:
            cursor = self._connection.execute(sql, list(parameters))
            names = [description[0] for description in cursor.description or ()]
            return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def _customer_country(value: Any) -> CountryCode:
        mapping = {"México": "MX", "Colombia": "CO", "Argentina": "AR"}
        country = mapping.get(str(value))
        if country is None:
            raise ConfigurationError("a cleaned customer has an unsupported country")
        return country

    @staticmethod
    def _currency(value: Any) -> str | None:
        if value is None:
            return None
        currency = str(value)
        if currency not in _CURRENCY_CODES:
            raise ConfigurationError("a cleaned row has an unsupported currency")
        return currency

    @classmethod
    def _entry(cls, row: Mapping[str, Any]) -> AccountEntry:
        try:
            status = TransactionStatus(str(row["transaction_status"]))
        except (KeyError, ValueError) as exc:
            raise ConfigurationError("a cleaned transaction has an invalid status") from exc
        transaction_country = row.get("transaction_country")
        country = _COUNTRY_CODES.get(str(transaction_country)) if transaction_country else None
        return AccountEntry(
            entry_reference=str(row["transaction_id"]),
            amount=_tool_amount(row.get("amount")),
            currency=cls._currency(row.get("currency")),
            credit_debit=None,
            status=status,
            booking_date=_transaction_date(row.get("transaction_date")),
            value_date=None,
            bank_transaction_code=None,
            remittance_information=None,
            merchant_category_code=None,
            country=country,
        )


def _find_source(root: Path, table: str) -> Path | None:
    """Match TSD-007's source selection: single Parquet, CSV, then table folder."""
    for candidate in (root / f"{table}.parquet", root / f"{table}.csv"):
        if candidate.is_file():
            return candidate
    folder = root / table
    if folder.is_dir() and (any(folder.rglob("*.parquet")) or any(folder.rglob("*.csv"))):
        return folder
    return None


def _source_files(source: Path) -> list[Path]:
    if source.is_file():
        return [source]
    parquet_files = sorted(source.rglob("*.parquet"))
    return parquet_files or sorted(source.rglob("*.csv"))


def _sql_string(path: Path) -> str:
    """Quote an explicit local path as a DuckDB string literal."""
    return "'" + str(path).replace("'", "''") + "'"


def _hash_source(root: Path, source: Path) -> str:
    digest = hashlib.sha256()
    for path in _source_files(source):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
    return digest.hexdigest()


def _optional_text(value: Any) -> str | None:
    return None if value is None else str(value)


def _source_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if type(value) is bool:
        return value
    if isinstance(value, (int, float, Decimal)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "1"}:
            return True
        if normalized in {"false", "0"}:
            return False
    raise ConfigurationError("a cleaned transaction has an invalid fraud flag")


def _tool_amount(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        amount = _AMOUNT_ADAPTER.validate_python(Decimal(str(value)))
    except (InvalidOperation, ValidationError):
        return None
    return amount


def _transaction_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        text = str(value)
        try:
            return date.fromisoformat(text)
        except ValueError:
            return datetime.fromisoformat(text).date()
    except ValueError as exc:
        raise ConfigurationError("a cleaned transaction has an invalid transaction_date") from exc


def _retry_reference(customer_id: str, idempotency_key: str) -> str:
    digest = hashlib.sha256(f"{customer_id}|{idempotency_key}".encode()).hexdigest()
    return digest[:10].upper()
