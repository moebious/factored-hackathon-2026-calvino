"""``BankTools``: the rules every tool call passes through, whatever the adapter (TSD-002).

Order of checks for a write: the session is present and unexpired; the record belongs to that
session's customer (the adapter refuses otherwise); a repeated idempotency key replays the first
result; the record is eligible (cancel only a Pending transfer or payment, retry only a
Declined one, neither if fraud-flagged); a hub-issued confirmation token matches this exact
action. Eligibility is decided here, from record facts; amount limits and the decision to ask a
person belong to the Gate (TSD-001), which is why a token exists only after an ``allow`` verdict
or a person's approval.

Idempotency keys are scoped to (customer, tool), so one customer can never read another's result by
reusing a key, and the same key with a different target is a conflict, not a replay.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

from calvino.tools.adapter import BankAdapter
from calvino.tools.confirmation import ConfirmationVerifier
from calvino.tools.contracts import (
    Account,
    AccountEntry,
    CancellationResponse,
    CustomerSummary,
    EntryRecord,
    Investigation,
    PaymentStatus,
    RetryResult,
    TransactionStatus,
)
from calvino.tools.errors import Rule, ToolRefusal
from calvino.tools.session import Session, require_session

# Only transfers and payments can be cancelled or retried; a card purchase or a deposit cannot.
_ACTIONABLE_TYPES = frozenset({"Transfer", "Payment"})
MAX_KEY_LENGTH = 128
MAX_REASON_LENGTH = 500


class BankTools:
    """The ten tools, as plain methods taking the session the hub attached."""

    def __init__(
        self,
        adapter: BankAdapter,
        verifier: ConfirmationVerifier,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._adapter = adapter
        self._verifier = verifier
        self._clock = clock or (lambda: datetime.now(UTC))
        self._replays: dict[tuple[str, str, str], tuple[str, Any]] = {}
        self._write_lock = threading.Lock()

    def _session(self, session: Session | None) -> Session:
        return require_session(session, self._clock())

    def get_customer_summary(self, session: Session | None) -> CustomerSummary:
        return self._adapter.get_customer_summary(self._session(session))

    def list_accounts(self, session: Session | None) -> list[Account]:
        return self._adapter.list_accounts(self._session(session))

    def get_account_entries(
        self,
        session: Session | None,
        account_id: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[AccountEntry]:
        _check_range(date_from, date_to)
        return self._adapter.get_account_entries(
            self._session(session), account_id, date_from, date_to
        )

    def get_entry_detail(self, session: Session | None, entry_reference: str) -> AccountEntry:
        return self._adapter.get_entry_detail(self._session(session), entry_reference)

    def get_payment_status(self, session: Session | None, entry_reference: str) -> PaymentStatus:
        return self._adapter.get_payment_status(self._session(session), entry_reference)

    def list_problem_transactions(
        self, session: Session | None, date_from: date | None = None, date_to: date | None = None
    ) -> list[AccountEntry]:
        _check_range(date_from, date_to)
        return self._adapter.list_problem_transactions(self._session(session), date_from, date_to)

    def get_investigation_status(self, session: Session | None, case_id: str) -> Investigation:
        return self._adapter.get_investigation_status(self._session(session), case_id)

    def request_cancellation(
        self,
        session: Session | None,
        entry_reference: str,
        idempotency_key: str,
        confirmation_token: str | None,
        reason: str = "Customer request",
    ) -> CancellationResponse:
        _check_text("reason", reason)
        return self._write(
            "request_cancellation",
            session,
            entry_reference,
            idempotency_key,
            confirmation_token,
            lambda s, record: _require_eligible(record, TransactionStatus.PENDING, "cancelled"),
            lambda s: self._adapter.cancel_payment(s, entry_reference, reason, idempotency_key),
        )

    def retry_payment(
        self,
        session: Session | None,
        entry_reference: str,
        idempotency_key: str,
        confirmation_token: str | None,
    ) -> RetryResult:
        return self._write(
            "retry_payment",
            session,
            entry_reference,
            idempotency_key,
            confirmation_token,
            lambda s, record: _require_eligible(record, TransactionStatus.DECLINED, "retried"),
            lambda s: self._adapter.retry_payment(s, entry_reference, idempotency_key),
        )

    def open_investigation(
        self,
        session: Session | None,
        entry_reference: str,
        reason: str,
        idempotency_key: str,
        confirmation_token: str | None,
    ) -> Investigation:
        _check_text("reason", reason)
        return self._write(
            "open_investigation",
            session,
            entry_reference,
            idempotency_key,
            confirmation_token,
            lambda s, record: None,
            lambda s: self._adapter.open_investigation(s, entry_reference, reason, idempotency_key),
        )

    def _write(
        self,
        tool: str,
        session: Session | None,
        entry_reference: str,
        idempotency_key: str,
        confirmation_token: str | None,
        check_eligible: Callable[[Session, EntryRecord], None],
        execute: Callable[[Session], Any],
    ) -> Any:
        s = self._session(session)
        _check_text("idempotency_key", idempotency_key, MAX_KEY_LENGTH)
        # Ownership first: another customer's record is refused before anything else is looked at.
        record = self._adapter.get_entry_record(s, entry_reference)
        with self._write_lock:
            replay_key = (s.customer_id, tool, idempotency_key)
            previous = self._replays.get(replay_key)
            if previous is not None:
                target, result = previous
                if target != entry_reference:
                    raise ToolRefusal(
                        Rule.IDEMPOTENCY_CONFLICT,
                        "this idempotency key was already used for a different request",
                    )
                return result
            check_eligible(s, record)
            if record.entry.amount is None or record.entry.currency is None:
                raise ToolRefusal(
                    Rule.SOURCE_INCOMPLETE,
                    "the source lacks the amount or currency required to confirm this action",
                )
            self._verifier.verify_and_consume(
                confirmation_token,
                customer_id=s.customer_id,
                action=tool,
                target_reference=entry_reference,
                amount=record.entry.amount,
                currency=record.entry.currency,
            )
            result = execute(s)
            self._replays[replay_key] = (entry_reference, result)
            return result


def _require_eligible(record: EntryRecord, required: TransactionStatus, verb: str) -> None:
    if record.fraud_flagged is None:
        raise ToolRefusal(
            Rule.SOURCE_INCOMPLETE,
            "the source lacks the fraud status required to authorize this action",
        )
    if record.fraud_flagged:
        raise ToolRefusal(
            Rule.FRAUD_FLAGGED, f"this transaction cannot be {verb}; a person must review it"
        )
    if record.transaction_type is None:
        raise ToolRefusal(
            Rule.SOURCE_INCOMPLETE,
            "the source lacks the transaction type required to authorize this action",
        )
    status = record.entry.status
    if record.transaction_type not in _ACTIONABLE_TYPES or status != required:
        raise ToolRefusal(
            Rule.INELIGIBLE,
            f"only a {required.value} transfer or payment can be {verb}; "
            f"this one is a {status.value} {record.transaction_type.lower()}",
        )


def _check_range(date_from: date | None, date_to: date | None) -> None:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise ToolRefusal(Rule.BAD_INPUT, "date_from must not be after date_to")


def _check_text(name: str, value: str, limit: int = MAX_REASON_LENGTH) -> None:
    if not value or not value.strip():
        raise ToolRefusal(Rule.BAD_INPUT, f"{name} must not be empty")
    if len(value) > limit:
        raise ToolRefusal(Rule.BAD_INPUT, f"{name} must be at most {limit} characters")
