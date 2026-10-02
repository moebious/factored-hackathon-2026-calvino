"""The bank adapter protocol (TSD-002).

One adapter per bank core: the dataset adapter for the demo, a second one for the swap test, the
real core in production. An adapter is thin data access: it receives a trusted ``Session`` (never a
customer id from a model), returns only that customer's records and refuses anything else with
``TOOL-NOT-OWNER`` or ``TOOL-NOT-FOUND``. Confirmation tokens, eligibility, idempotency and session
expiry are enforced once, in ``BankTools``, so a new adapter cannot forget them. Every adapter must
pass the conformance suite in ``tests/calvino/tools/test_conformance.py``.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol

from calvino.tools.contracts import (
    Account,
    AccountEntry,
    CancellationResponse,
    CustomerSummary,
    EntryRecord,
    Investigation,
    PaymentStatus,
    RetryResult,
)
from calvino.tools.session import Session


class BankAdapter(Protocol):
    """One method per tool, plus ``get_entry_record`` for the facts eligibility needs."""

    def get_customer_summary(self, session: Session) -> CustomerSummary: ...

    def list_accounts(self, session: Session) -> list[Account]: ...

    def get_account_entries(
        self, session: Session, account_id: str, date_from: date | None, date_to: date | None
    ) -> list[AccountEntry]: ...

    def get_entry_detail(self, session: Session, entry_reference: str) -> AccountEntry: ...

    def get_entry_record(self, session: Session, entry_reference: str) -> EntryRecord:
        """Internal: the entry with its type and fraud flag. Ownership-checked, never sent out."""
        ...

    def get_payment_status(self, session: Session, entry_reference: str) -> PaymentStatus: ...

    def list_problem_transactions(
        self, session: Session, date_from: date | None, date_to: date | None
    ) -> list[AccountEntry]:
        """Declined, Pending and Reversed entries; status only, never ``response_code``."""
        ...

    def cancel_payment(
        self, session: Session, entry_reference: str, reason: str, idempotency_key: str
    ) -> CancellationResponse:
        """Cancel a pending payment. Callers have already checked eligibility and the token."""
        ...

    def retry_payment(
        self, session: Session, entry_reference: str, idempotency_key: str
    ) -> RetryResult:
        """Retry a declined payment as a new one. Eligibility and token are already checked."""
        ...

    def open_investigation(
        self, session: Session, entry_reference: str, reason: str, idempotency_key: str
    ) -> Investigation: ...

    def get_investigation_status(self, session: Session, case_id: str) -> Investigation: ...
