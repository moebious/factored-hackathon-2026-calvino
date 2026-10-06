"""The acceptance record and the leakage guard for the fine-tuning export (TSD-020, T-202).

Fine-tuning may see one thing only: the accepted T-106 train split. This module decides
whether an export is allowed to proceed, and says why when it is not.

- **The acceptance record** (``evaluation/message-set/v1/acceptance.json``) is the machine-readable
  form of TSD-019's P4 accept rule: a split is accepted when its reviewed sample carries at most
  one defect. Only the maintainer writes the real file, because it records a review judgment;
  this module only reads and checks it. It names the SHA-256 of the split's message file, so any
  edit made after acceptance invalidates it ("reviewed messages are never silently edited into
  passing").
- **The guard** runs the five checks TSD-020 names and always reports all five, so a run record
  can list each result. It **fails closed**: a comparison set it cannot see (calibration, test,
  their seed registries) is a failed check, never a skipped one, because a check that cannot
  look proves nothing.

Offenders are reported as ids and reasons, never as message text.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from calvino.classifiers.laya import needs_human_question, workflow_area_question
from calvino.data.labels import GoldRecord
from calvino.data.leakage import (
    SeedEntry,
    check_l1_customer_isolation,
    check_l4_generation_isolation,
    check_l5_gold_held_out,
)
from calvino.data.message_set import (
    LANGUAGE_VARIANTS,
    MessageRow,
    SeedRow,
    is_near_duplicate,
)

# <repo>/evaluation/message-set/v1/acceptance.json, found from this file (src/calvino/data/).
DEFAULT_ACCEPTANCE_PATH = (
    Path(__file__).resolve().parents[3] / "evaluation" / "message-set" / "v1" / "acceptance.json"
)

# TSD-019 P4: a split is accepted iff its reviewed sample carries at most this many defects.
MAX_ACCEPTED_DEFECTS = 1

# The five checks, in the order TSD-020 lists them. FineTuneRunRecord requires each by name.
CHECK_NAMES = ("wrong-split", "text-overlap", "shared-keys", "portuguese-row", "unknown-label")

# The options of the two first-slice questions, read from the builders so a changed builder
# changes what counts as a known label.
NEEDS_HUMAN_OPTIONS = tuple(needs_human_question()["criteria"])
AREA_OPTIONS = tuple(workflow_area_question()["criteria"])
_HUMAN_NEEDED, _CAN_HANDLE = NEEDS_HUMAN_OPTIONS

_SHA256 = re.compile(r"[0-9a-f]{64}")


def needs_human_option(needs_person: bool) -> str:
    """The ``needs_human`` option a ``needs_person`` label maps to (TSD-020 label mapping)."""
    return _HUMAN_NEEDED if needs_person else _CAN_HANDLE


class SplitAcceptance(BaseModel):
    """The maintainer's acceptance of one split, tied to the exact bytes reviewed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    accepted: bool
    defects: int = Field(ge=0)
    reviewed_sample: int = Field(ge=0)
    prompt_version: str = Field(min_length=1)
    messages_sha256: str
    accepted_on: str

    @field_validator("messages_sha256")
    @classmethod
    def _full_digest(cls, value: str) -> str:
        if not _SHA256.fullmatch(value):
            raise ValueError("messages_sha256 must be 64 lowercase hex characters")
        return value

    @field_validator("accepted_on")
    @classmethod
    def _iso_date(cls, value: str) -> str:
        date.fromisoformat(value)
        return value


class AcceptanceRecord(BaseModel):
    """The contents of ``acceptance.json``: one entry per accepted split."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    set_version: str = Field(min_length=1)
    splits: dict[str, SplitAcceptance]


def load_acceptance(path: str | Path = DEFAULT_ACCEPTANCE_PATH) -> AcceptanceRecord | None:
    """Read ``acceptance.json``; ``None`` when the file does not exist (nothing is accepted)."""
    target = Path(path)
    if not target.is_file():
        return None
    return AcceptanceRecord.model_validate_json(target.read_text(encoding="utf-8"))


def load_message_rows(path: str | Path) -> tuple[list[MessageRow], list[str]]:
    """Read one message file; also return the ids of rows in a non-Spanish variant.

    Those rows cannot validate as ``MessageRow`` (the schema is Spanish only), so they are set
    aside by id for the ``portuguese-row`` check instead of crashing the load.
    """
    rows: list[MessageRow] = []
    non_spanish: list[str] = []
    with Path(path).open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            data = json.loads(line)
            if data.get("language_variant") not in LANGUAGE_VARIANTS:
                non_spanish.append(str(data.get("msg_id", f"line {number}")))
                continue
            try:
                rows.append(MessageRow.model_validate(data))
            except ValidationError as error:
                raise SystemExit(f"{path}:{number}: invalid message row: {error}") from error
    return rows, non_spanish


@dataclass(frozen=True)
class GuardCheck:
    """One check's result: whether it passed and, if not, which ids and why."""

    check: str
    passed: bool
    offenders: tuple[str, ...] = ()


@dataclass(frozen=True)
class GuardResult:
    """All five checks. ``passed`` is true only when every one passed."""

    checks: tuple[GuardCheck, ...]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    def summary(self) -> str:
        """One line per failed check with its offenders; empty when everything passed."""
        return "\n".join(
            f"{check.check}: {len(check.offenders)} offender(s): " + "; ".join(check.offenders)
            for check in self.checks
            if not check.passed
        )


@dataclass(frozen=True)
class GuardInputs:
    """Everything the guard compares the train split against.

    ``None`` for a comparison set means it could not be read, which fails the check that
    needs it (fail closed).
    """

    train: Sequence[MessageRow]
    train_seeds: Sequence[SeedRow]
    set_version: str
    messages_sha256: str  # SHA-256 of the train message file as read
    acceptance: AcceptanceRecord | None
    calibration: Sequence[MessageRow] | None
    test: Sequence[MessageRow] | None
    calibration_seeds: Sequence[SeedRow] | None
    test_seeds: Sequence[SeedRow] | None
    gold: Sequence[GoldRecord]
    eval_messages: Sequence[tuple[str, str]]  # (case id, message) from evaluation/cases/
    portuguese_messages: Sequence[tuple[str, str]] = ()
    non_spanish_train_ids: Sequence[str] = ()


def _wrong_split(inputs: GuardInputs) -> GuardCheck:
    offenders = [
        f"{row.msg_id}: split is {row.split}" for row in inputs.train if row.split != "train"
    ]
    entry = inputs.acceptance.splits.get("train") if inputs.acceptance else None
    if inputs.acceptance is None:
        offenders.append("acceptance record missing")
    elif entry is None:
        offenders.append("acceptance record has no train entry")
    else:
        if inputs.acceptance.set_version != inputs.set_version:
            offenders.append(
                f"acceptance is for set {inputs.acceptance.set_version}, not {inputs.set_version}"
            )
        if not entry.accepted:
            offenders.append("train split is not accepted")
        if entry.defects > MAX_ACCEPTED_DEFECTS:
            offenders.append(f"{entry.defects} defects exceed the limit of {MAX_ACCEPTED_DEFECTS}")
        if entry.messages_sha256 != inputs.messages_sha256:
            offenders.append("train messages changed after acceptance (SHA-256 differs)")
    return GuardCheck("wrong-split", not offenders, tuple(offenders))


def _text_overlap(inputs: GuardInputs) -> GuardCheck:
    offenders: list[str] = []
    others: list[tuple[str, str, str]] = []  # (set name, id, text)
    for name, rows in (("calibration", inputs.calibration), ("test", inputs.test)):
        if rows is None:
            offenders.append(f"{name} messages unavailable, overlap cannot be checked")
        else:
            others += [(name, row.msg_id, row.message) for row in rows]
    others += [("gold", g.gold_id, g.message) for g in inputs.gold]
    others += [("evaluation-cases", cid, text) for cid, text in inputs.eval_messages]
    others += [("portuguese", pid, text) for pid, text in inputs.portuguese_messages]
    for row in inputs.train:
        for name, other_id, text in others:
            if is_near_duplicate(row.message, text):
                offenders.append(f"{row.msg_id} overlaps {name} {other_id}")
    return GuardCheck("text-overlap", not offenders, tuple(offenders))


def _shared_keys(inputs: GuardInputs) -> GuardCheck:
    offenders: list[str] = []
    train_by_key = {seed.seed_key: seed for seed in inputs.train_seeds}
    for row in inputs.train:
        if row.seed_key not in train_by_key:
            offenders.append(f"{row.msg_id}: seed {row.seed_key} is not in the train registry")
    for name, seeds in (("calibration", inputs.calibration_seeds), ("test", inputs.test_seeds)):
        if seeds is None:
            offenders.append(f"{name} seed registry unavailable, isolation cannot be checked")
    if inputs.calibration_seeds is None or inputs.test_seeds is None:
        return GuardCheck("shared-keys", False, tuple(offenders))

    # Only the seeds that actually feed a train message count as train's.
    used = {k: train_by_key[k] for k in {row.seed_key for row in inputs.train} if k in train_by_key}
    calibration, test = inputs.calibration_seeds, inputs.test_seeds
    customers = {
        "train": {seed.customer_hash for seed in used.values()},
        "calibration": {seed.customer_hash for seed in calibration},
        "test": {seed.customer_hash for seed in test},
    }
    entries = [SeedEntry(seed.seed_key, "train", seed.prompt_id) for seed in used.values()]
    entries += [SeedEntry(seed.seed_key, "calibration", seed.prompt_id) for seed in calibration]
    entries += [SeedEntry(seed.seed_key, "test", seed.prompt_id) for seed in test]
    violations = check_l1_customer_isolation(customers) + check_l4_generation_isolation(entries)
    # Gold has no customer hash; its seed_ref is "table + key" or "hand-written", so only a real
    # key can collide with a seed key.
    violations += check_l5_gold_held_out(
        set(),
        {gold.seed_ref for gold in inputs.gold},
        set(used) | customers["train"],
        {seed.seed_key for seed in calibration} | customers["calibration"],
    )
    offenders += [f"{v.rule_id}: {v.detail}" for v in violations]
    return GuardCheck("shared-keys", not offenders, tuple(offenders))


def _portuguese_row(inputs: GuardInputs) -> GuardCheck:
    offenders = tuple(f"{msg_id}: non-Spanish variant" for msg_id in inputs.non_spanish_train_ids)
    return GuardCheck("portuguese-row", not offenders, offenders)


def _unknown_label(inputs: GuardInputs) -> GuardCheck:
    offenders = [
        f"{row.msg_id}: workflow_area {row.labels.workflow_area!r} is not an option"
        for row in inputs.train
        if row.labels.workflow_area is not None and row.labels.workflow_area not in AREA_OPTIONS
    ]
    return GuardCheck("unknown-label", not offenders, tuple(offenders))


def run_leakage_guard(inputs: GuardInputs) -> GuardResult:
    """Run all five checks, in ``CHECK_NAMES`` order, and report every result."""
    return GuardResult(
        (
            _wrong_split(inputs),
            _text_overlap(inputs),
            _shared_keys(inputs),
            _portuguese_row(inputs),
            _unknown_label(inputs),
        )
    )
