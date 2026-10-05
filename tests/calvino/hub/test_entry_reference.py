"""Unit tests for the deterministic entry-reference detector.

No model calls, network or dataset; all references synthetic.
"""

import pytest

from calvino.hub.entry_reference import ENTRY_REF_RE, extract_entry_references


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Mi pago E-MX-002 sigue pendiente, ¿qué pasa?", ("E-MX-002",)),
        ("¿Cuál es el estado de mi transferencia E-MX-002?", ("E-MX-002",)),
        ("Reintenta la transferencia E-US-001", ("E-US-001",)),
        ("Cancela E-MX-002 y explícame E-MX-003", ("E-MX-002", "E-MX-003")),
        ("E-MX-002 y E-MX-002 otra vez", ("E-MX-002",)),
        ("(E-CO-001).", ("E-CO-001",)),
    ],
)
def test_extracts_references_in_order(message: str, expected: tuple[str, ...]):
    assert extract_entry_references(message) == expected


@pytest.mark.parametrize(
    "message",
    [
        "",
        "Tengo un problema",
        "¿Me recomiendas una receta de tamales?",
        "E-MX-02",  # too short
        "E-MX-0002",  # too long
        "X-MX-002",  # wrong prefix
        "e-mx-002",  # the template agent only focuses uppercase refs
        "E-MX-00A",  # not digits
    ],
)
def test_ignores_non_references(message: str):
    assert extract_entry_references(message) == ()


def test_pattern_is_the_template_agent_focus_pattern():
    """The router and the agent stay anchored on the same reference."""
    from calvino.hub import template_agent

    assert template_agent._ENTRY_REF_RE.pattern == ENTRY_REF_RE.pattern
