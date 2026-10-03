"""Tests for calvino.hub.playbook: the versioned stuck-payments playbook file (decision 24)."""

from __future__ import annotations

import textwrap

import pytest
from pydantic import ValidationError

from calvino.hub.playbook import DEFAULT_PLAYBOOK_PATH, Playbook, StatusGuidance, load_playbook

MINIMAL_YAML = """
version: v1
workflow: stuck-payments
statuses:
  Pending:
    explain: on hold, not settled yet
    actions: [request_cancellation]
    escalate_when: value date passed
  Declined:
    explain: refused, money never left
    actions: [retry_payment]
    escalate_when: reason missing
  Reversed:
    explain: returned to the account
    actions: []
    escalate_when: customer disputes it
"""


def write(tmp_path, text: str):
    path = tmp_path / "playbook.yaml"
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return path


def test_shipped_playbook_loads_and_is_versioned() -> None:
    playbook = load_playbook()
    assert playbook.version == "v1"
    assert playbook.workflow == "stuck-payments"
    assert set(playbook.statuses) == {"Pending", "Declined", "Reversed"}


def test_shipped_playbook_actions_match_the_stage_tools() -> None:
    playbook = load_playbook()
    assert playbook.guidance("Pending").actions == ("request_cancellation",)
    assert playbook.guidance("Declined").actions == ("retry_payment",)
    # A reversal is final: nothing to offer on the payment itself.
    assert playbook.guidance("Reversed").actions == ()


def test_default_path_points_at_the_shipped_file() -> None:
    assert DEFAULT_PLAYBOOK_PATH.name == "stuck-payments.yaml"
    assert DEFAULT_PLAYBOOK_PATH.exists()


def test_minimal_playbook_loads(tmp_path) -> None:
    playbook = load_playbook(write(tmp_path, MINIMAL_YAML))
    assert isinstance(playbook, Playbook)
    assert playbook.guidance("Pending").escalate_when == "value date passed"


def test_missing_status_is_rejected(tmp_path) -> None:
    text = MINIMAL_YAML.replace(
        """  Reversed:
    explain: returned to the account
    actions: []
    escalate_when: customer disputes it
""",
        "",
    )
    with pytest.raises(ValidationError, match="missing statuses"):
        load_playbook(write(tmp_path, text))


def test_unknown_status_is_rejected(tmp_path) -> None:
    text = (
        MINIMAL_YAML
        + """  Settled:
    explain: completed
    escalate_when: never
"""
    )
    with pytest.raises(ValidationError, match="outside the workflow"):
        load_playbook(write(tmp_path, text))


def test_unknown_action_is_rejected() -> None:
    with pytest.raises(ValidationError, match="unknown playbook actions"):
        StatusGuidance(explain="x", actions=("refund_customer",), escalate_when="y")


def test_unknown_keys_are_rejected(tmp_path) -> None:
    text = MINIMAL_YAML + "owner: analyst\n"
    with pytest.raises(ValidationError):
        load_playbook(write(tmp_path, text))


def test_guidance_for_unknown_status_raises(tmp_path) -> None:
    playbook = load_playbook(write(tmp_path, MINIMAL_YAML))
    with pytest.raises(KeyError, match="Settled"):
        playbook.guidance("Settled")


def test_playbook_is_frozen(tmp_path) -> None:
    playbook = load_playbook(write(tmp_path, MINIMAL_YAML))
    with pytest.raises(ValidationError):
        playbook.version = "v2"  # type: ignore[misc]
