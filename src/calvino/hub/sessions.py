"""Trusted test sessions (TSD-009): the hub issues them, chat never types them.

The demo and the tests authenticate a persona (a fixture customer) through the
hub, which issues an opaque token and keeps the ``Session`` it belongs to. A
customer number typed in chat is never an identity: the tools only trust a
``Session`` the issuer resolved from its own token. The token itself stays
harness-side: it is attached to tool calls out of band, never placed in graph
state, an ``AgentRequest`` or a log record (only ``session_ref_for(token)``).
"""

from __future__ import annotations

import secrets
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta

from calvino.records import session_ref_for
from calvino.tools.session import Session

# Short-lived on purpose: a demo session should not outlive a coffee break,
# and expiry is the fail-closed path the tools already enforce.
DEFAULT_SESSION_TTL = timedelta(minutes=30)


class TrustedSessionIssuer:
    """Maps demo personas to sessions; the only source of ``Session`` objects."""

    def __init__(
        self,
        personas: Mapping[str, str],
        session_ttl: timedelta = DEFAULT_SESSION_TTL,
        token_factory: Callable[[], str] = secrets.token_urlsafe,
    ) -> None:
        if not personas:
            raise ValueError("the issuer needs at least one persona")
        self._personas = dict(personas)
        self._session_ttl = session_ttl
        self._token_factory = token_factory
        self._sessions: dict[str, Session] = {}

    def personas(self) -> tuple[str, ...]:
        """The persona names the demo can sign in as."""
        return tuple(self._personas)

    def issue(self, persona: str, now: datetime | None = None) -> tuple[str, str]:
        """Sign a persona in: returns ``(token, session_ref)``.

        The ``Session`` stays inside the issuer; callers get the opaque token
        (to attach to tool calls) and the hashed reference (to log). An
        unknown persona raises rather than falling back to anyone.
        """
        if persona not in self._personas:
            raise KeyError(f"unknown persona {persona!r}")
        token = self._token_factory()
        while token in self._sessions:
            token = self._token_factory()
        moment = now or datetime.now(UTC)
        self._sessions[token] = Session(
            customer_id=self._personas[persona],
            expires_at=moment + self._session_ttl,
        )
        return token, session_ref_for(token)

    def resolve(self, context: object, now: datetime | None = None) -> Session | None:
        """The ``SessionResolver`` view: a token (or None) to a live ``Session``.

        Matches the resolver signature the tools were built with
        (``Callable[[Any], Session | None]``); an unknown or expired token
        resolves to None, and the tools' own ``require_session`` then refuses.
        """
        if not isinstance(context, str):
            return None
        session = self._sessions.get(context)
        if session is None:
            return None
        if (now or datetime.now(UTC)) >= session.expires_at:
            return None
        return session
