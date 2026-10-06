"""Deterministic entry-reference detector for the route anchor.

Finds the fixture entry references (``E-MX-002``) a customer message names, so
the router can anchor the turn on a concrete bank entry before Laya's
phrasing-sensitive scores are read. The pattern is the canonical one: the
template agent focuses with this same expression, and sharing it keeps the
router and the agent anchored on the same reference. Pure string matching, no
model calls, no tools: ownership is still enforced downstream by the tools.
"""

from __future__ import annotations

import re

# Fixture entry references ("E-MX-002") a demo message may name. Uppercase by
# construction: the fixture mints them uppercase, and the template agent only
# focuses what this same expression matches, so the router must not see more.
ENTRY_REF_RE = re.compile(r"\bE-[A-Z]{2}-\d{3}\b")


def extract_entry_references(text: str) -> tuple[str, ...]:
    """Distinct entry references in order of appearance (empty when none).

    Deduplicated so "E-MX-002 y E-MX-002" anchors once; order kept so the
    first mention wins, exactly as the template agent focuses.
    """
    if not text:
        return ()
    seen: dict[str, None] = {}
    for match in ENTRY_REF_RE.finditer(text):
        seen.setdefault(match.group())
    return tuple(seen)
