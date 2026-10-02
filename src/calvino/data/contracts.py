"""Data contracts for the tables Calvino uses (TSD-007, T-102).

Each table has a row model (the columns Calvino reads, with their types) and a
``TableContract`` (primary key, foreign keys, required columns). ``RULES`` holds the
table-level checks from DATA.md as SQL predicates, each with a severity: ``error`` fails
the audit, ``known_defect`` is counted and reported but never fails it, because DATA.md
says known defects are reported, not cleaned away.

Row models ignore columns they do not name, so the same contracts apply to the raw
files and to a cleaned layer.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Severity(StrEnum):
    """How a failed check counts."""

    ERROR = "error"
    KNOWN_DEFECT = "known_defect"


CURRENCIES = ("MXN", "COP", "ARS", "USD")
COUNTRIES = ("México", "Colombia", "Argentina")
TRANSACTION_STATUSES = ("Approved", "Declined", "Pending", "Reversed")


class _Row(BaseModel):
    """Base row model: frozen, ignores unnamed columns, reads NaN as missing."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def _nan_to_none(cls, data: Any) -> Any:
        # Parquet and CSV readers return NaN for missing floats; the contracts treat it as None.
        if isinstance(data, dict):
            return {
                k: None if isinstance(v, float) and math.isnan(v) else v for k, v in data.items()
            }
        return data


def _one_of(value: str | None, allowed: tuple[str, ...], name: str) -> str | None:
    if value is not None and value not in allowed:
        raise ValueError(f"{name} {value!r} is not one of {', '.join(allowed)}")
    return value


class Customer(_Row):
    customer_id: str = Field(min_length=1)
    country: str
    segment: str | None = None
    detected_accent: str | None = None
    credit_score: float | None = None

    @field_validator("country")
    @classmethod
    def _country(cls, v: str) -> str:
        return _one_of(v, COUNTRIES, "country") or v


class Product(_Row):
    product_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    product_type: str | None = None
    currency: str | None = None

    @field_validator("currency")
    @classmethod
    def _currency(cls, v: str | None) -> str | None:
        return _one_of(v, CURRENCIES, "currency")


class Transaction(_Row):
    transaction_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    product_id: str | None = None
    transaction_date: date | datetime | None = None
    transaction_type: str | None = None
    transaction_status: str
    amount: float | None = None
    currency: str | None = None
    amount_usd: float | None = None
    # Null in about 5% of rows in every status, Approved included: a deliberate defect,
    # never a failure signal (DATA.md, reports/data-quality f05).
    response_code: str | None = None
    transaction_country: str | None = None
    is_fraud: bool | None = None
    channel: str | None = None

    @field_validator("transaction_status")
    @classmethod
    def _status(cls, v: str) -> str:
        return _one_of(v, TRANSACTION_STATUSES, "transaction_status") or v

    @field_validator("currency")
    @classmethod
    def _currency(cls, v: str | None) -> str | None:
        return _one_of(v, CURRENCIES, "currency")


class Complaint(_Row):
    complaint_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    creation_date: date | datetime | None = None
    category: str | None = None
    case_type: str | None = None
    status: str | None = None
    claimed_amount: float | None = None
    currency: str | None = None
    # Null on every row in the full data: complaints link to calls by customer and time.
    origin_interaction_id: str | None = None
    sla_breached: bool | None = None
    resolution_days: float | None = None
    # An amount, not a flag: granted means non-null (reports/baseline).
    compensation_granted: float | None = None

    @field_validator("currency")
    @classmethod
    def _currency(cls, v: str | None) -> str | None:
        return _one_of(v, CURRENCIES, "currency")


class CallCenterInteraction(_Row):
    interaction_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    agent_id: str | None = None
    interaction_date: date | datetime | None = None
    channel: str | None = None
    contact_reason: str | None = None
    reason_category: str
    was_resolved: bool | None = None
    was_escalated: bool | None = None
    requires_followup: bool | None = None
    duration_seconds: float | None = None
    wait_time_seconds: float | None = None


class ExchangeRate(_Row):
    date: date | datetime
    source_currency: str
    target_currency: str
    exchange_rate: float = Field(gt=0)


class ServiceAgent(_Row):
    agent_id: str = Field(min_length=1)
    assigned_branch_id: str | None = None


class Branch(_Row):
    branch_id: str = Field(min_length=1)


@dataclass(frozen=True)
class ForeignKey:
    """A column that must exist in a parent table; orphans fail unless marked a known defect."""

    column: str
    parent: str
    parent_column: str
    severity: Severity = Severity.ERROR


@dataclass(frozen=True)
class TableContract:
    """What the audit checks for one table, beyond its rules."""

    name: str
    model: type[_Row]
    primary_key: tuple[str, ...]
    required: tuple[str, ...]
    foreign_keys: tuple[ForeignKey, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Rule:
    """A table-level check from DATA.md: ``predicate`` selects the rows that violate it."""

    rule_id: str
    table: str
    severity: Severity
    predicate: str
    meaning: str


def _in(values: tuple[str, ...]) -> str:
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


TABLES: dict[str, TableContract] = {
    t.name: t
    for t in (
        TableContract("customers", Customer, ("customer_id",), ("customer_id", "country")),
        TableContract(
            "products",
            Product,
            ("product_id",),
            ("product_id", "customer_id"),
            (ForeignKey("customer_id", "customers", "customer_id"),),
        ),
        TableContract(
            "transactions",
            Transaction,
            ("transaction_id",),
            ("transaction_id", "customer_id", "transaction_status"),
            (
                ForeignKey("customer_id", "customers", "customer_id"),
                ForeignKey("product_id", "products", "product_id"),
            ),
        ),
        TableContract(
            "complaints",
            Complaint,
            ("complaint_id",),
            ("complaint_id", "customer_id"),
            (ForeignKey("customer_id", "customers", "customer_id"),),
        ),
        TableContract(
            "call_center_interactions",
            CallCenterInteraction,
            ("interaction_id",),
            ("interaction_id", "customer_id", "reason_category"),
            (
                ForeignKey("customer_id", "customers", "customer_id"),
                ForeignKey("agent_id", "service_agents", "agent_id"),
            ),
        ),
        TableContract(
            "daily_exchange_rates",
            ExchangeRate,
            ("date", "source_currency", "target_currency"),
            ("date", "source_currency", "target_currency", "exchange_rate"),
        ),
        TableContract(
            "service_agents",
            ServiceAgent,
            ("agent_id",),
            ("agent_id",),
            # Only 2 of 833 values exist in branches; dropping orphans would delete most
            # agents and the interactions that reference them (DATA.md).
            (ForeignKey("assigned_branch_id", "branches", "branch_id", Severity.KNOWN_DEFECT),),
        ),
        TableContract("branches", Branch, ("branch_id",), ("branch_id",)),
    )
}


RULES: tuple[Rule, ...] = (
    Rule(
        "TX-STATUS",
        "transactions",
        Severity.ERROR,
        f"transaction_status NOT IN {_in(TRANSACTION_STATUSES)}",
        "status is one of Approved, Declined, Pending, Reversed",
    ),
    Rule(
        "TX-CURRENCY",
        "transactions",
        Severity.ERROR,
        f"currency NOT IN {_in(CURRENCIES)}",
        "currency is MXN, COP, ARS or USD",
    ),
    Rule(
        "TX-RESPONSE-CODE-NULL",
        "transactions",
        Severity.KNOWN_DEFECT,
        "response_code IS NULL",
        "null response_code: about 5% in every status, never a failure signal",
    ),
    Rule(
        "TX-COUNTRY-MEXICO",
        "transactions",
        Severity.KNOWN_DEFECT,
        "transaction_country = 'Mexico'",
        "unaccented 'Mexico' label, merged into México (ISO 3166 MX) when used",
    ),
    Rule(
        "CU-COUNTRY",
        "customers",
        Severity.ERROR,
        f"country NOT IN {_in(COUNTRIES)}",
        "customers are in México, Colombia or Argentina; there are no Brazilian customers",
    ),
    Rule(
        "PR-CURRENCY",
        "products",
        Severity.ERROR,
        f"currency NOT IN {_in(CURRENCIES)}",
        "product currency is MXN, COP, ARS or USD when present",
    ),
    Rule(
        "CP-AMOUNT-NO-CURRENCY",
        "complaints",
        Severity.KNOWN_DEFECT,
        "claimed_amount IS NOT NULL AND currency IS NULL",
        "a claimed amount without a currency cannot be converted to USD",
    ),
    Rule(
        "CP-ORIGIN-NULL",
        "complaints",
        Severity.KNOWN_DEFECT,
        "origin_interaction_id IS NULL",
        "no complaint records its originating interaction; link by customer and time",
    ),
    Rule(
        "CI-REASON-REPEATS",
        "call_center_interactions",
        Severity.KNOWN_DEFECT,
        "contact_reason = reason_category",
        "contact_reason repeats reason_category: there is one reason level",
    ),
    Rule(
        "FX-RATE-POSITIVE",
        "daily_exchange_rates",
        Severity.ERROR,
        "exchange_rate <= 0",
        "exchange rates are strictly positive",
    ),
)


def rules_for(table: str) -> tuple[Rule, ...]:
    """The rules that apply to one table."""
    return tuple(r for r in RULES if r.table == table)
