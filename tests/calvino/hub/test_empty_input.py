"""Unit tests for the empty-input detector (HR-EMPTY-INPUT, DESIGN 6.1)."""

import pytest

from calvino.hub.empty_input import has_content


@pytest.mark.parametrize("message", ["", "   ", "\n\t", "😀", "😀 👍", "?!...", "—", "​"])
def test_no_letter_or_digit_has_no_content(message):
    assert has_content(message) is False


@pytest.mark.parametrize(
    "message", ["hola", "¿?a", "7", "😀 pago", "atenção", "支付失败", "Ñ", "E-MX-002"]
)
def test_any_letter_or_digit_has_content(message):
    assert has_content(message) is True
