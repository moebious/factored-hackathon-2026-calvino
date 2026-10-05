"""Deterministic empty-input detector for HR-EMPTY-INPUT (DESIGN 6.1).

A message with no letter and no digit (empty, spaces only, emoji only, punctuation
only) carries nothing to classify. Laya still returns scores for it (0.57 for "stuck
payment" on an empty message, measured in the T-303 policy v4 run), so the hub asks
the customer to say more before Laya is consulted. This does not try to judge
garbled text that contains letters; that needs a definition nobody has written yet.
"""

from __future__ import annotations

import unicodedata


def has_content(message: str) -> bool:
    """True when the message holds at least one letter or digit (any script)."""
    return any(unicodedata.category(char)[0] in {"L", "N"} for char in message)
