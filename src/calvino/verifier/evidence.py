"""Evidence for the deterministic checks (TSD-004): the facts a reply may cite.

The hub builds one ``Evidence`` per verification from this session's tool
results, the confirmed read-backs and the markers that belong to other
customers. The code checks compare the reply only against this model, never
against anything the reply itself claims, so a reply can never vouch for
itself (DESIGN.md 4.4).

``from_tool_results`` walks the ISO 20022-aligned payloads of TSD-002 by field
name, so the evidence is complete even when a future tool adds a payload the
hub author did not think about here.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from calvino.tools.contracts import TransactionStatus

# Field names in the TSD-002 contracts that carry citable facts. Walking by
# name (not per tool) keeps the evidence complete as contracts grow.
_AMOUNT_FIELDS = ("amount", "balance")
_DATE_FIELDS = ("booking_date", "value_date")
_DATETIME_FIELDS = ("opened_at",)
_MERCHANT_FIELD = "remittance_information"
_STATUS_FIELD = "status"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ToolResult(_Frozen):
    """One tool result of this session, as the contract model serialized it."""

    tool: str = Field(min_length=1)
    payload: dict


class Evidence(_Frozen):
    """Everything the deterministic checks compare the reply against.

    - ``amounts``/``dates``/``merchants``/``statuses``: the citable facts from
      this session's tool results.
    - ``customer_language``: the language the reply must be in.
    - ``read_backs``: action ids that were verified by reading them back; a
      claimed action outside this set fails the read-back check.
    - ``forbidden_markers``: identifiers and names that belong to another
      customer (collected by the hub from refusals and context); any of them
      appearing in the reply fails the privacy check. This check is only as
      complete as the markers the hub collects; the grounding criteria behind
      Laya and the judge back it up.
    """

    amounts: frozenset[Decimal] = Field(default_factory=frozenset)
    dates: frozenset[date] = Field(default_factory=frozenset)
    merchants: frozenset[str] = Field(default_factory=frozenset)
    statuses: frozenset[TransactionStatus] = Field(default_factory=frozenset)
    customer_language: Literal["es", "pt"] = "es"
    read_backs: frozenset[str] = Field(default_factory=frozenset)
    forbidden_markers: frozenset[str] = Field(default_factory=frozenset)


def _walk(payload: dict):
    """Yield every (key, value) pair in a nested payload, depth-first."""
    for key, value in payload.items():
        yield key, value
        if isinstance(value, dict):
            yield from _walk(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    yield from _walk(item)


def _to_status(value: object) -> TransactionStatus | None:
    try:
        return TransactionStatus(str(value))
    except ValueError:
        # Account.status and Investigation.status are not transaction statuses;
        # only the transaction ones are citable payment statuses.
        return None


def evidence_from_tool_results(
    results: list[ToolResult] | tuple[ToolResult, ...],
    *,
    customer_language: Literal["es", "pt"] = "es",
    read_backs: frozenset[str] | set[str] | tuple[str, ...] = frozenset(),
    forbidden_markers: frozenset[str] | set[str] | tuple[str, ...] = frozenset(),
) -> Evidence:
    """Collect the citable facts from tool result payloads.

    Amounts arrive as strings in the contracts (never floats); a value that is
    not a decimal is skipped rather than guessed at. Dates arrive as ISO
    strings; ``opened_at`` contributes its date part.
    """
    amounts: set[Decimal] = set()
    dates: set[date] = set()
    merchants: set[str] = set()
    statuses: set[TransactionStatus] = set()

    for result in results:
        for key, value in _walk(result.payload):
            if value is None:
                continue
            if key in _AMOUNT_FIELDS:
                try:
                    amounts.add(Decimal(str(value)))
                except InvalidOperation:
                    continue
            elif key in _DATE_FIELDS:
                dates.add(date.fromisoformat(str(value)))
            elif key in _DATETIME_FIELDS:
                dates.add(datetime.fromisoformat(str(value)).date())
            elif key == _MERCHANT_FIELD and str(value).strip():
                merchants.add(str(value).strip())
            elif key == _STATUS_FIELD:
                status = _to_status(value)
                if status is not None:
                    statuses.add(status)

    return Evidence(
        amounts=frozenset(amounts),
        dates=frozenset(dates),
        merchants=frozenset(merchants),
        statuses=frozenset(statuses),
        customer_language=customer_language,
        read_backs=frozenset(read_backs),
        forbidden_markers=frozenset(forbidden_markers),
    )
