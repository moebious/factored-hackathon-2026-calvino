"""The customer session as the tools see it (TSD-002).

The hub authenticates the customer and attaches a ``Session`` to each tool call out of band, through
the server's request context. It is never a tool argument, so a model cannot name another customer
(AGENTS.md: the customer's session token never passes through a model). The tools only trust a
``Session`` returned by the resolver they were built with.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from calvino.tools.errors import Rule, ToolRefusal


class Session(BaseModel):
    """An authenticated customer session, issued by the hub."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    customer_id: str
    expires_at: datetime

    @field_validator("customer_id")
    @classmethod
    def _customer_id_not_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("customer_id must not be empty")
        return value

    @field_validator("expires_at")
    @classmethod
    def _expires_at_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("expires_at must include a timezone")
        return value


# Given the MCP request context, returns the session the hub attached, or None when there is none.
# The hub supplies it (for example by validating a header on the HTTP transport); a model cannot.
SessionResolver = Callable[[Any], Session | None]


def require_session(session: Session | None, now: datetime | None = None) -> Session:
    """Return ``session`` if it is present and unexpired, else refuse (fail closed)."""
    if session is None:
        raise ToolRefusal(Rule.NO_SESSION, "no customer session is attached to this call")
    if (now or datetime.now(UTC)) >= session.expires_at:
        raise ToolRefusal(Rule.SESSION_EXPIRED, "the customer session has expired")
    return session
