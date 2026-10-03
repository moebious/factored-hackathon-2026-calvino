"""Playbook loader (TSD-009): the pydantic model of ``playbooks/stuck-payments.yaml``.

The playbook is the one source for the agent's guidance and the verifier's "valid next step"
criterion (decision 24), so neither can drift. Versioned like the policy: a released file is
never edited, and every logged decision carries the playbook version it was made under.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

# <repo>/playbooks/stuck-payments.yaml, found from this file (src/calvino/hub/playbook.py).
DEFAULT_PLAYBOOK_PATH = Path(__file__).resolve().parents[3] / "playbooks" / "stuck-payments.yaml"

# The write tools an action may name (DESIGN 6.1: act and investigate stages). Reads are
# always available and are not playbook actions.
PLAYBOOK_ACTIONS = frozenset({"request_cancellation", "retry_payment", "open_investigation"})

# The statuses the stuck-payments workflow handles (DESIGN 6.1).
WORKFLOW_STATUSES = frozenset({"Pending", "Declined", "Reversed"})


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StatusGuidance(_Frozen):
    """What the agent explains, offers and escalates on for one transaction status."""

    explain: str = Field(min_length=1)
    actions: tuple[str, ...] = ()
    escalate_when: str = Field(min_length=1)

    @model_validator(mode="after")
    def _actions_are_known(self) -> StatusGuidance:
        unknown = set(self.actions) - PLAYBOOK_ACTIONS
        if unknown:
            raise ValueError(f"unknown playbook actions: {sorted(unknown)}")
        return self


class Playbook(_Frozen):
    """One versioned workflow playbook."""

    version: str = Field(min_length=1)
    workflow: str = Field(min_length=1)
    statuses: dict[str, StatusGuidance]

    @model_validator(mode="after")
    def _covers_the_workflow(self) -> Playbook:
        missing = WORKFLOW_STATUSES - set(self.statuses)
        if missing:
            raise ValueError(f"playbook is missing statuses: {sorted(missing)}")
        unknown = set(self.statuses) - WORKFLOW_STATUSES
        if unknown:
            raise ValueError(f"playbook has statuses outside the workflow: {sorted(unknown)}")
        return self

    def guidance(self, status: str) -> StatusGuidance:
        """The guidance for one status; an unknown status raises rather than guessing."""
        if status not in self.statuses:
            raise KeyError(f"the playbook does not cover status {status!r}")
        return self.statuses[status]


def load_playbook(path: str | Path = DEFAULT_PLAYBOOK_PATH) -> Playbook:
    """Read and validate a playbook file; an invalid file raises rather than loading partially."""
    with Path(path).open(encoding="utf-8") as handle:
        return Playbook.model_validate(yaml.safe_load(handle))
