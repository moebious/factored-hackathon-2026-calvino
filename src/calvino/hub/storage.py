"""Persistent and memory storage for parked cases and thread mappings (TSD-025, T-401)."""

from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict


class CaseRecord(BaseModel):
    """Durable record of a parked case and its associated graph thread."""

    model_config = ConfigDict(frozen=True)

    case_ref: str
    thread_id: str
    persona: str
    status: Literal["pending_approval", "in_investigation", "refused", "resolved"]
    reason_rule_id: str
    created_at: str
    customer_message: str
    entry_reference: str | None = None
    amount: str | None = None
    currency: str | None = None
    target_action: Literal["cancel_payment", "retry_payment", "open_investigation"] | None = None
    awaiting_ref: str | None = None
    gate_verdict: str | None = None


class CaseStore(Protocol):
    """Protocol for storing and retrieving durable cases across restarts."""

    def put(self, case: CaseRecord) -> None:
        """Store or update a case record."""
        ...

    def get_by_ref(self, ref: str) -> CaseRecord | None:
        """Retrieve a case by awaiting_ref or case_ref."""
        ...

    def get_by_case_ref(self, case_ref: str) -> CaseRecord | None:
        """Retrieve a case strictly by case_ref."""
        ...

    def list_all(self) -> list[CaseRecord]:
        """List all stored cases ordered by created_at."""
        ...

    def update_status(self, case_ref: str, status: str) -> None:
        """Update the status of an existing case."""
        ...


class SqliteCaseStore:
    """Thread-safe SQLite-backed store for durable cases and parked thread mappings."""

    def __init__(self, db_path: Path | str) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._setup()

    def _setup(self) -> None:
        with self._lock, self._conn:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS cases (
                    case_ref TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    persona TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason_rule_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    customer_message TEXT NOT NULL,
                    entry_reference TEXT,
                    amount TEXT,
                    currency TEXT,
                    target_action TEXT,
                    awaiting_ref TEXT,
                    gate_verdict TEXT
                )
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cases_awaiting_ref ON cases(awaiting_ref)
            """)

    def put(self, case: CaseRecord) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO cases (
                    case_ref, thread_id, persona, status, reason_rule_id,
                    created_at, customer_message, entry_reference, amount,
                    currency, target_action, awaiting_ref, gate_verdict
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(case_ref) DO UPDATE SET
                    thread_id=excluded.thread_id,
                    persona=excluded.persona,
                    status=excluded.status,
                    reason_rule_id=excluded.reason_rule_id,
                    created_at=excluded.created_at,
                    customer_message=excluded.customer_message,
                    entry_reference=excluded.entry_reference,
                    amount=excluded.amount,
                    currency=excluded.currency,
                    target_action=excluded.target_action,
                    awaiting_ref=excluded.awaiting_ref,
                    gate_verdict=excluded.gate_verdict
            """,
                (
                    case.case_ref,
                    case.thread_id,
                    case.persona,
                    case.status,
                    case.reason_rule_id,
                    case.created_at,
                    case.customer_message,
                    case.entry_reference,
                    case.amount,
                    case.currency,
                    case.target_action,
                    case.awaiting_ref,
                    case.gate_verdict,
                ),
            )

    def _row_to_record(self, row: tuple) -> CaseRecord:
        return CaseRecord(
            case_ref=row[0],
            thread_id=row[1],
            persona=row[2],
            status=row[3],
            reason_rule_id=row[4],
            created_at=row[5],
            customer_message=row[6],
            entry_reference=row[7],
            amount=row[8],
            currency=row[9],
            target_action=row[10],
            awaiting_ref=row[11],
            gate_verdict=row[12],
        )

    def get_by_ref(self, ref: str) -> CaseRecord | None:
        with self._lock, self._conn:
            cur = self._conn.execute(
                """
                SELECT case_ref, thread_id, persona, status, reason_rule_id,
                       created_at, customer_message, entry_reference, amount,
                       currency, target_action, awaiting_ref, gate_verdict
                FROM cases
                WHERE awaiting_ref = ? OR case_ref = ?
                LIMIT 1
            """,
                (ref, ref),
            )
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_record(row)

    def get_by_case_ref(self, case_ref: str) -> CaseRecord | None:
        with self._lock, self._conn:
            cur = self._conn.execute(
                """
                SELECT case_ref, thread_id, persona, status, reason_rule_id,
                       created_at, customer_message, entry_reference, amount,
                       currency, target_action, awaiting_ref, gate_verdict
                FROM cases
                WHERE case_ref = ?
                LIMIT 1
            """,
                (case_ref,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_record(row)

    def list_all(self) -> list[CaseRecord]:
        with self._lock, self._conn:
            cur = self._conn.execute("""
                SELECT case_ref, thread_id, persona, status, reason_rule_id,
                       created_at, customer_message, entry_reference, amount,
                       currency, target_action, awaiting_ref, gate_verdict
                FROM cases
                ORDER BY created_at ASC
            """)
            return [self._row_to_record(row) for row in cur.fetchall()]

    def update_status(self, case_ref: str, status: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE cases SET status = ? WHERE case_ref = ?",
                (status, case_ref),
            )


class MemoryCaseStore:
    """In-memory case store for transient testing."""

    def __init__(self) -> None:
        self._cases: dict[str, CaseRecord] = {}

    def put(self, case: CaseRecord) -> None:
        self._cases[case.case_ref] = case

    def get_by_ref(self, ref: str) -> CaseRecord | None:
        for case in self._cases.values():
            if case.awaiting_ref == ref or case.case_ref == ref:
                return case
        return None

    def get_by_case_ref(self, case_ref: str) -> CaseRecord | None:
        return self._cases.get(case_ref)

    def list_all(self) -> list[CaseRecord]:
        return sorted(self._cases.values(), key=lambda c: c.created_at)

    def update_status(self, case_ref: str, status: str) -> None:
        case = self._cases.get(case_ref)
        if case:
            self._cases[case_ref] = CaseRecord(
                case_ref=case.case_ref,
                thread_id=case.thread_id,
                persona=case.persona,
                status=status,  # type: ignore[arg-type]
                reason_rule_id=case.reason_rule_id,
                created_at=case.created_at,
                customer_message=case.customer_message,
                entry_reference=case.entry_reference,
                amount=case.amount,
                currency=case.currency,
                target_action=case.target_action,
                awaiting_ref=case.awaiting_ref,
                gate_verdict=case.gate_verdict,
            )


def create_case_store(data_dir: Path | str | None = None) -> CaseStore:
    """Create a SQLite case store when data_dir is provided or CALVINO_DATA_DIR is set."""
    path = data_dir or os.environ.get("CALVINO_DATA_DIR")
    if not path:
        return MemoryCaseStore()
    return SqliteCaseStore(Path(path) / "hub-cases.sqlite")
