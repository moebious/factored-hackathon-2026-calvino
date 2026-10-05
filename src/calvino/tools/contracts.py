"""ISO 20022-aligned shapes for the bank tools (TSD-002).

"Aligned", not "compliant": each model borrows the structure and the element names of the ISO 20022
message it is modelled on, and every field says which element it corresponds to. Codes follow ISO
4217 (currency), ISO 3166 (country) and ISO 18245 (merchant category). The JSON Schemas in
``contracts/tools/`` are generated from these models (``scripts/export_tool_schemas.py``) and a test
fails if they drift.

``EntryRecord`` is internal: it carries the facts the tools need to decide eligibility (type, fraud
flag) and is never returned to a caller, so a model or a customer never sees the fraud flag.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

CurrencyCode = Annotated[str, Field(pattern=r"^[A-Z]{3}$", description="ISO 4217 currency code")]
CountryCode = Annotated[str, Field(pattern=r"^[A-Z]{2}$", description="ISO 3166-1 alpha-2 country")]
# Amounts are decimals serialized as strings, never floats, so no rounding error reaches a customer.
Amount = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=2)]


class TransactionStatus(StrEnum):
    """The dataset's ``transaction_status``. The only source of a payment's status (DATA.md):
    a null ``response_code`` is a deliberate defect on about 5% of rows and never means a failure.
    Modelled on the pacs.002 status codes (PDNG pending, ACSC settled, RJCT rejected)."""

    PENDING = "Pending"
    APPROVED = "Approved"
    DECLINED = "Declined"
    REVERSED = "Reversed"


class CreditDebit(StrEnum):
    """camt.053 ``CdtDbtInd``."""

    CREDIT = "CRDT"
    DEBIT = "DBIT"


class InvestigationStatus(StrEnum):
    """Status of an investigation case (camt.027 request, camt.029 resolution)."""

    OPEN = "Open"
    IN_REVIEW = "InReview"
    RESOLVED = "Resolved"
    CLOSED = "Closed"


class CancellationOutcome(StrEnum):
    """camt.029 outcome of a cancellation request."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"


class _Contract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CustomerSummary(_Contract):
    """The signed-in customer, as seen by the agent (no ISO message; a business-partner extract)."""

    customer_id: str
    display_name: str | None = None
    country: CountryCode
    segment: str | None = None
    account_count: int | None = Field(default=None, ge=0)


class Account(_Contract):
    """An account or linked-product projection (camt.052 ``Acct`` shape)."""

    account_id: str = Field(description="Acct/Id; source product id in the cleaned-table adapter")
    account_type: str | None = Field(default=None, description="Acct/Tp")
    currency: CurrencyCode | None = Field(default=None, description="Acct/Ccy")
    status: str | None = None
    balance: Decimal | None = Field(
        default=None, max_digits=18, decimal_places=2, description="Bal/Amt"
    )


class AccountEntry(_Contract):
    """An account entry, with nullable fields when a source has no matching element."""

    entry_reference: str = Field(description="Ntry/NtryRef")
    amount: Amount | None = Field(default=None, description="Ntry/Amt")
    currency: CurrencyCode | None = Field(default=None, description="Ntry/Amt@Ccy")
    credit_debit: CreditDebit | None = Field(default=None, description="Ntry/CdtDbtInd")
    status: TransactionStatus = Field(description="Ntry/Sts")
    booking_date: date | None = Field(
        default=None,
        description=(
            "Ntry/BookgDt; projects the source transaction date, not a distinct bank booking date"
        ),
    )
    value_date: date | None = Field(default=None, description="Ntry/ValDt")
    bank_transaction_code: str | None = Field(
        default=None, description="Ntry/BkTxCd (domain-family-subfamily)"
    )
    remittance_information: str | None = Field(
        default=None, description="Ntry/NtryDtls/TxDtls/RmtInf/Ustrd"
    )
    merchant_category_code: str | None = Field(
        default=None, pattern=r"^[0-9]{4}$", description="ISO 18245 merchant category"
    )
    country: CountryCode | None = Field(default=None, description="Transaction country")


class PaymentStatus(_Contract):
    """The status of one payment (pacs.002 ``TxInfAndSts``)."""

    original_reference: str = Field(description="OrgnlTxId")
    status: TransactionStatus = Field(description="TxSts")
    reason: str | None = Field(default=None, description="StsRsnInf/Rsn")


class Investigation(_Contract):
    """An investigation case (camt.027 claim, camt.029 resolution)."""

    case_id: str = Field(description="Assgnmt/Id")
    related_entry_reference: str = Field(description="Undrlyg/OrgnlTxRef")
    reason: str = Field(description="Case/Rsn")
    status: InvestigationStatus = Field(description="Sts/Conf")
    opened_at: datetime = Field(description="Assgnmt/CreDtTm")
    resolution: str | None = Field(default=None, description="RslvdCase/Rslvn")
    next_step: str | None = Field(
        default=None, description="What happens next, in words for the customer"
    )


class CancellationResponse(_Contract):
    """A cancellation request (camt.056) and its answer (camt.029)."""

    original_reference: str = Field(description="Undrlyg/OrgnlTxRef")
    reason: str = Field(description="Case/Rsn")
    requested_by: str = Field(description="Assgnr: the customer who asked")
    outcome: CancellationOutcome = Field(description="CxlStsRspn/Conf")
    rejection_reason: str | None = Field(default=None, description="CxlStsRspn/RsnCd")
    simulated: bool = Field(description="True when the adapter did not move real money")
    message: str


class RetryResult(_Contract):
    """The new payment created by retrying a declined one."""

    original_reference: str
    new_payment: PaymentStatus
    simulated: bool = Field(description="True when the adapter did not move real money")
    message: str


class EntryRecord(BaseModel):
    """Internal: an entry plus the facts eligibility needs. Never returned to a caller."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entry: AccountEntry
    customer_id: str
    account_id: str | None = None
    transaction_type: str | None = None
    fraud_flagged: bool | None = None
    status_reason: str | None = None
    # Kept only to document that it exists and is ignored: status never derives from it.
    response_code: str | None = None


# The models the JSON Schemas are generated for, by file name.
SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "customer-summary": CustomerSummary,
    "account": Account,
    "account-entry": AccountEntry,
    "payment-status": PaymentStatus,
    "investigation": Investigation,
    "cancellation-response": CancellationResponse,
    "retry-result": RetryResult,
}
