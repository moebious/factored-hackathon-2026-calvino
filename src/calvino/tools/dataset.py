"""The dataset adapter: a ``BankAdapter`` over a small in-memory dataset (TSD-002).

The data comes from a JSON file (the synthetic fixture in ``tests/fixtures/bank/`` for tests and the
demo). Writes are simulated: they append to ``action_log`` and to the adapter's own case list and
never change the loaded records, and every result says it is simulated.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from calvino.tools.contracts import (
    Account,
    AccountEntry,
    CancellationOutcome,
    CancellationResponse,
    CustomerSummary,
    EntryRecord,
    Investigation,
    InvestigationStatus,
    PaymentStatus,
    RetryResult,
    TransactionStatus,
)
from calvino.tools.errors import Rule, ToolRefusal
from calvino.tools.session import Session

_PROBLEM_STATUSES = frozenset(
    {TransactionStatus.DECLINED, TransactionStatus.PENDING, TransactionStatus.REVERSED}
)


def _short_hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:10].upper()


class DatasetAdapter:
    """Serves one customer's records at a time, from data loaded once and never modified."""

    def __init__(self, data: dict[str, Any], clock: Callable[[], datetime] | None = None) -> None:
        self._customers: dict[str, dict[str, Any]] = {
            c["customer_id"]: c for c in data["customers"]
        }
        self._accounts = [Account.model_validate(_account_fields(a)) for a in data["accounts"]]
        self._account_owner = {a["account_id"]: a["customer_id"] for a in data["accounts"]}
        self._records: dict[str, EntryRecord] = {}
        for raw in data["entries"]:
            record = EntryRecord.model_validate(_entry_fields(raw))
            self._records[record.entry.entry_reference] = record
        self._cases: dict[str, tuple[str, Investigation]] = {}
        for raw in data.get("investigations", []):
            self._cases[raw["case_id"]] = (
                raw["customer_id"],
                Investigation.model_validate(_case_fields(raw)),
            )
        self._clock = clock or (lambda: datetime.now(UTC))
        self.action_log: list[dict[str, str]] = []

    @classmethod
    def from_file(cls, path: Path, clock: Callable[[], datetime] | None = None) -> DatasetAdapter:
        return cls(json.loads(path.read_text(encoding="utf-8")), clock)

    def get_customer_summary(self, session: Session) -> CustomerSummary:
        customer = self._customers.get(session.customer_id)
        if customer is None:
            raise ToolRefusal(Rule.NOT_FOUND, "no customer for this session")
        count = sum(
            1 for a in self._accounts if self._account_owner[a.account_id] == session.customer_id
        )
        return CustomerSummary(
            customer_id=customer["customer_id"],
            display_name=customer["display_name"],
            country=customer["country"],
            segment=customer["segment"],
            account_count=count,
        )

    def list_accounts(self, session: Session) -> list[Account]:
        return [
            a for a in self._accounts if self._account_owner[a.account_id] == session.customer_id
        ]

    def get_account_entries(
        self, session: Session, account_id: str, date_from: date | None, date_to: date | None
    ) -> list[AccountEntry]:
        owner = self._account_owner.get(account_id)
        if owner is None:
            raise ToolRefusal(Rule.NOT_FOUND, "no such account")
        if owner != session.customer_id:
            raise ToolRefusal(
                Rule.NOT_OWNER, "the account does not belong to this session's customer"
            )
        return [
            r.entry
            for r in self._records.values()
            if r.account_id == account_id and _in_range(r.entry.booking_date, date_from, date_to)
        ]

    def get_entry_record(self, session: Session, entry_reference: str) -> EntryRecord:
        record = self._records.get(entry_reference)
        if record is None:
            raise ToolRefusal(Rule.NOT_FOUND, "no such entry")
        if record.customer_id != session.customer_id:
            raise ToolRefusal(
                Rule.NOT_OWNER, "the entry does not belong to this session's customer"
            )
        return record

    def get_entry_detail(self, session: Session, entry_reference: str) -> AccountEntry:
        return self.get_entry_record(session, entry_reference).entry

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
        # Status only. A null response_code is on ~5% of rows in every status and means nothing.
        return [
            r.entry
            for r in self._records.values()
            if r.customer_id == session.customer_id
            and r.entry.status in _PROBLEM_STATUSES
            and _in_range(r.entry.booking_date, date_from, date_to)
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
        new_reference = f"RTY-{_short_hash(session.customer_id, idempotency_key)}"
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
                original_reference=new_reference, status=TransactionStatus.PENDING
            ),
            simulated=True,
            message="SIMULATED: the retry was recorded in the adapter's action log only; "
            "no real payment was created.",
        )

    def open_investigation(
        self, session: Session, entry_reference: str, reason: str, idempotency_key: str
    ) -> Investigation:
        self.get_entry_record(session, entry_reference)
        case_id = f"CASE-{_short_hash(session.customer_id, idempotency_key)}"
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


def _in_range(value: date, date_from: date | None, date_to: date | None) -> bool:
    return (date_from is None or value >= date_from) and (date_to is None or value <= date_to)


def _account_fields(raw: dict[str, Any]) -> dict[str, Any]:
    return {k: raw[k] for k in ("account_id", "account_type", "currency", "status", "balance")}


def _case_fields(raw: dict[str, Any]) -> dict[str, Any]:
    keys = ("case_id", "related_entry_reference", "reason", "status", "opened_at", "next_step")
    return {k: raw[k] for k in keys if k in raw}


_ENTRY_KEYS = (
    "entry_reference",
    "amount",
    "currency",
    "credit_debit",
    "status",
    "booking_date",
    "value_date",
    "bank_transaction_code",
    "remittance_information",
    "merchant_category_code",
    "country",
)


def _entry_fields(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "entry": {k: raw[k] for k in _ENTRY_KEYS if k in raw},
        "customer_id": raw["customer_id"],
        "account_id": raw["account_id"],
        "transaction_type": raw["transaction_type"],
        "fraud_flagged": raw.get("fraud_flagged", False),
        "status_reason": raw.get("status_reason"),
        "response_code": raw.get("response_code"),
    }
