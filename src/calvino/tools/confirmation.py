"""Hub-issued confirmation tokens for write tools (TSD-002).

A write tool acts only with a token the hub issued after an ``allow`` verdict from the Gate or a
person's approval. A token is bound to one customer, one action, one target payment, one amount and
currency, expires after a short time and works once, so it is never a pass for "any
cancellation".

``ConfirmationVerifier`` is the interface the tools depend on. ``HmacConfirmationVerifier`` signs
with HMAC-SHA256 under a key the hub and the server share (read from an environment variable, never
defaulted). ``FakeConfirmationVerifier`` is for tests. Used-token memory is per process: a
deployment with several server processes needs a shared store (a production gap).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Protocol

from calvino.tools.errors import ConfigurationError, Rule, ToolRefusal

KEY_ENV_VAR = "CALVINO_CONFIRMATION_KEY"
MIN_KEY_BYTES = 32
DEFAULT_TTL = timedelta(minutes=5)


class ConfirmationVerifier(Protocol):
    """Checks a confirmation token for one exact action and consumes it."""

    def verify_and_consume(
        self,
        token: str | None,
        *,
        customer_id: str,
        action: str,
        target_reference: str,
        amount: Decimal,
        currency: str,
    ) -> None:
        """Return normally if the token is valid for exactly this action; raise ``ToolRefusal``."""


def confirmation_key_from_env(env: dict[str, str] | None = None) -> bytes:
    """Read the shared key from the environment; refuse to start if it is missing or too short."""
    value = (os.environ if env is None else env).get(KEY_ENV_VAR, "")
    key = value.encode("utf-8")
    if len(key) < MIN_KEY_BYTES:
        raise ConfigurationError(
            f"{KEY_ENV_VAR} must be set to a secret of at least {MIN_KEY_BYTES} bytes; "
            "the server does not start without it"
        )
    return key


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


class HmacConfirmationVerifier:
    """Issues (hub side) and verifies (tool side) HMAC-signed, single-use, expiring tokens."""

    def __init__(
        self,
        key: bytes,
        *,
        ttl: timedelta = DEFAULT_TTL,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if len(key) < MIN_KEY_BYTES:
            raise ConfigurationError(f"the confirmation key must be at least {MIN_KEY_BYTES} bytes")
        self._key = key
        self._ttl = ttl
        self._clock = clock or (lambda: datetime.now(UTC))
        self._used: dict[str, datetime] = {}
        self._lock = threading.Lock()

    def issue(
        self,
        *,
        customer_id: str,
        action: str,
        target_reference: str,
        amount: Decimal,
        currency: str,
    ) -> str:
        """Hub side: sign a token for exactly one action."""
        claims = {
            "c": customer_id,
            "a": action,
            "t": target_reference,
            "m": str(amount),
            "u": currency,
            "e": int((self._clock() + self._ttl).timestamp()),
            "n": secrets.token_hex(16),
        }
        body = _b64(json.dumps(claims, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        return f"{body}.{self._sign(body)}"

    def verify_and_consume(
        self,
        token: str | None,
        *,
        customer_id: str,
        action: str,
        target_reference: str,
        amount: Decimal,
        currency: str,
    ) -> None:
        if not token:
            raise ToolRefusal(
                Rule.TOKEN_MISSING, "this action needs a hub-issued confirmation token"
            )
        body, _, signature = token.partition(".")
        if not body or not hmac.compare_digest(signature, self._sign(body)):
            raise ToolRefusal(Rule.TOKEN_INVALID, "the confirmation token is not valid")
        try:
            claims = json.loads(_unb64(body))
            token_amount = Decimal(claims["m"])
            expires_at = datetime.fromtimestamp(int(claims["e"]), UTC)
            nonce = str(claims["n"])
            matches = (
                claims["c"] == customer_id
                and claims["a"] == action
                and claims["t"] == target_reference
                and token_amount == amount
                and claims["u"] == currency
            )
        except (ValueError, KeyError, TypeError, InvalidOperation):
            raise ToolRefusal(Rule.TOKEN_INVALID, "the confirmation token is not valid") from None

        now = self._clock()
        if now >= expires_at:
            raise ToolRefusal(Rule.TOKEN_EXPIRED, "the confirmation token has expired")
        if not matches:
            raise ToolRefusal(
                Rule.TOKEN_MISMATCH, "the confirmation token was not issued for this exact action"
            )
        with self._lock:
            self._used = {n: exp for n, exp in self._used.items() if exp > now}
            if nonce in self._used:
                raise ToolRefusal(Rule.TOKEN_USED, "the confirmation token was already used")
            self._used[nonce] = expires_at

    def _sign(self, body: str) -> str:
        return hmac.new(self._key, body.encode("ascii"), hashlib.sha256).hexdigest()


class FakeConfirmationVerifier:
    """For tests: accepts only tokens granted for exactly one action, once."""

    def __init__(self) -> None:
        self._granted: set[tuple[str, str, str, str, Decimal, str]] = set()

    def grant(
        self,
        *,
        customer_id: str,
        action: str,
        target_reference: str,
        amount: Decimal,
        currency: str,
        token: str = "fake-token",
    ) -> str:
        self._granted.add((token, customer_id, action, target_reference, amount, currency))
        return token

    def issue(
        self,
        *,
        customer_id: str,
        action: str,
        target_reference: str,
        amount: Decimal,
        currency: str,
    ) -> str:
        """The hub-side name, mirroring ``HmacConfirmationVerifier.issue``."""
        return self.grant(
            customer_id=customer_id,
            action=action,
            target_reference=target_reference,
            amount=amount,
            currency=currency,
        )

    def verify_and_consume(
        self,
        token: str | None,
        *,
        customer_id: str,
        action: str,
        target_reference: str,
        amount: Decimal,
        currency: str,
    ) -> None:
        if not token:
            raise ToolRefusal(
                Rule.TOKEN_MISSING, "this action needs a hub-issued confirmation token"
            )
        key = (token, customer_id, action, target_reference, amount, currency)
        if key not in self._granted:
            raise ToolRefusal(Rule.TOKEN_INVALID, "the confirmation token is not valid")
        self._granted.discard(key)
