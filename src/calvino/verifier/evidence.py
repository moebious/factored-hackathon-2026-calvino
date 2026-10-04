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

import re
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

# How much of the customer's own words the judge is shown. The criterion only needs to know what
# was asked, not who the customer is.
_QUESTION_MAX_CHARS = 240
_REDACTED = "<redacted>"


_NUMBER_IN_TEXT = re.compile(r"\d[\d.,]*\d|\d")


def _redact_amounts(text: str, amounts: frozenset[Decimal]) -> str:
    """Replace amounts by value, not by spelling.

    The contracts carry "5000.00" and a customer types "5000", or "5.000,50" where the tool says
    "5000.50". Matching the literal string let every one of those through, which is the whole
    disclosure this function exists to prevent, so each number in the prose is parsed and compared
    numerically instead. A single digit is left alone: it is far more often a count ("5 dias") than
    a figure, and redacting every "1" would make the digest unreadable without hiding anything.
    """
    if not amounts:
        return text

    def replace(match: re.Match[str]) -> str:
        raw = match.group(0)
        if len(raw) < 2 and not any(sep in raw for sep in ".,"):
            return raw
        try:
            value = Decimal(raw.replace(",", ""))
        except InvalidOperation:
            return raw
        return "<amount>" if value in amounts else raw

    return _NUMBER_IN_TEXT.sub(replace, text)


def redact_question(
    message: str,
    *,
    forbidden_markers: frozenset[str] = frozenset(),
    amounts: frozenset[Decimal] = frozenset(),
    dates: frozenset[date] = frozenset(),
    merchants: frozenset[str] = frozenset(),
) -> str | None:
    """Reduce the customer's message to what the judge needs, and no more.

    ``question-fully-answered`` is unjudgeable without the question, but NFR-1 says customer text
    for decisions stays with a self-hosted model and that external models receive only redacted,
    minimal context. The judge is an external model producing blocking verdicts, so it is on the
    decision side of that line, and free text can carry anything a customer typed. So the harness
    redacts before the judge sees anything, without asking a model to do it:

    - markers belonging to other customers become ``<redacted>``, which also keeps the privacy
      criterion honest for the question itself;
    - amounts, dates and merchants become typed placeholders, because their values already travel
      separately as structured evidence, so repeating them in prose adds exposure and no fact.
      Amounts are matched by value rather than by spelling, since "5000.00" in a payload and
      "5000" in a message are the same disclosure;
    - the result is whitespace-collapsed and capped, since length is itself a disclosure.

    Returns ``None`` for an empty message, so "no question" and "a redacted question" stay
    distinguishable in the prompt.
    """
    text = " ".join(message.split())
    if not text:
        return None

    for marker in sorted(forbidden_markers, key=len, reverse=True):
        if marker.strip():
            text = text.replace(marker.strip(), _REDACTED)
    for merchant in sorted(merchants, key=len, reverse=True):
        if merchant.strip():
            text = text.replace(merchant.strip(), "<merchant>")
    text = _redact_amounts(text, amounts)
    for day in sorted((d.isoformat() for d in dates), key=len, reverse=True):
        text = text.replace(day, "<date>")

    if len(text) > _QUESTION_MAX_CHARS:
        text = text[: _QUESTION_MAX_CHARS - 1].rstrip() + "…"
    return text


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
    # The customer's message, already redacted by redact_question. question-fully-answered cannot
    # be judged without it, and NFR-1 says an external model sees redacted, minimal context, so
    # the hub passes the digest and never the raw message. Named for the speaker because the hub's
    # own turn output already uses "question" for the clarification question the agent asks.
    customer_question: str | None = None


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
    message: str | None = None,
) -> Evidence:
    """Collect the citable facts from tool result payloads.

    Amounts arrive as strings in the contracts (never floats); a value that is
    not a decimal is skipped rather than guessed at. Dates arrive as ISO
    strings; ``opened_at`` contributes its date part.

    ``message`` is the customer's own words for this turn, kept only as a
    redacted digest. Redaction happens here, after the facts are collected and
    before anything is returned, so no caller can forget it and no caller can
    reach the raw text by a different route.
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
        customer_question=redact_question(
            message or "",
            forbidden_markers=frozenset(forbidden_markers),
            amounts=frozenset(amounts),
            dates=frozenset(dates),
            merchants=frozenset(merchants),
        ),
    )
