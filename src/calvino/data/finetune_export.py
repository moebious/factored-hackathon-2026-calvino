"""Export the accepted train split as fine-tuning items (TSD-020, T-202).

One row per (message, question) for the two first-slice questions, ``needs_human`` and
``workflow_area``, asked exactly as ``calvino.classifiers`` builds them: same instructions, same
criteria, same option order (option order is positional in Laya). A target is the labelled
option; the notebook turns it into a one-hot distribution.

The export refuses to write anything unless the leakage guard (``finetune_guard``) passes. Its
output is deterministic: the same inputs give byte-identical files, so a run record can name the
exact items a checkpoint saw.

**The temperature hold-out lives here, by message.** The vendor loop fits laya's own
temperatures on a slice it never trains on, and the running system applies those baked
temperatures (Calvino's calibration module is offline), so the slice matters. The notebook's
random hold-out is by item; with two questions per message it could train on one question of a
message and fit the temperature on the other. Here a message's items go together: each row gets
a ``role`` of ``train`` or ``laya_temperature_holdout``, sized like the notebook's rule (the
smaller of 400 and 10% of the items), and the notebook only reads the role.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from calvino.classifiers.laya import needs_human_question, workflow_area_question
from calvino.data.finetune_guard import (
    GuardInputs,
    GuardResult,
    load_acceptance,
    load_message_rows,
    needs_human_option,
    run_leakage_guard,
)
from calvino.data.labels import GoldRecord
from calvino.data.message_set import MessageRow, SeedRow
from calvino.data.seed_registry import load_seed_registry

EXPORTER_VERSION = 1
QUESTION_NEEDS_HUMAN = "needs_human"
QUESTION_WORKFLOW_AREA = "workflow_area"
ROLE_TRAIN = "train"
ROLE_HOLDOUT = "laya_temperature_holdout"

# The vendor notebook's rule: min(400, 10% of the items) go to the temperature fit.
HOLDOUT_MAX_ITEMS = 400
HOLDOUT_FRACTION = 10
# Fixed and versioned: the hold-out is chosen by hashing this with each message id.
HOLDOUT_SALT = "t202-temperature-holdout-v1"

_REVIEWED = ("pass", "corrected")


class LeakageError(Exception):
    """The leakage guard failed, so nothing was written."""

    def __init__(self, result: GuardResult):
        super().__init__("leakage guard failed:\n" + result.summary())
        self.result = result


def question_definitions() -> dict[str, dict]:
    """The two first-slice questions, built today, in a fixed order."""
    return {
        QUESTION_NEEDS_HUMAN: needs_human_question(),
        QUESTION_WORKFLOW_AREA: workflow_area_question(),
    }


def question_schema_sha256() -> str:
    """SHA-256 of the canonical JSON of the two question definitions.

    Option order is part of the meaning, so keys are not sorted inside a question. A change to
    either builder changes this hash, and a checkpoint trained on different wording is a
    different experiment.
    """
    canonical = json.dumps(question_definitions(), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _holdout_message_ids(message_item_counts: dict[str, int]) -> set[str]:
    """Whole messages, in a fixed pseudo-random order, until the notebook's item count is met."""
    total = sum(message_item_counts.values())
    wanted = min(HOLDOUT_MAX_ITEMS, total // HOLDOUT_FRACTION)
    ordered = sorted(
        message_item_counts,
        key=lambda msg_id: hashlib.sha256(f"{HOLDOUT_SALT}:{msg_id}".encode()).hexdigest(),
    )
    chosen: set[str] = set()
    taken = 0
    for msg_id in ordered:
        if taken >= wanted:
            break
        chosen.add(msg_id)
        taken += message_item_counts[msg_id]
    return chosen


def build_items(rows: Sequence[MessageRow]) -> tuple[list[dict], dict[str, int]]:
    """The export rows, and the exclusions counted on the way.

    A message with no workflow area (an unclassifiable one) gives a ``needs_human`` item only:
    it stays out of the area head, as the rubric says.
    """
    definitions = question_definitions()
    excluded: dict[str, int] = {}
    pending: list[tuple[MessageRow, str, str]] = []
    for row in sorted(rows, key=lambda r: r.msg_id):
        pending.append((row, QUESTION_NEEDS_HUMAN, needs_human_option(row.labels.needs_person)))
        if row.labels.workflow_area is None:
            reason = "workflow area unset (no area item)"
            excluded[reason] = excluded.get(reason, 0) + 1
        else:
            pending.append((row, QUESTION_WORKFLOW_AREA, row.labels.workflow_area))
    per_message: dict[str, int] = {}
    for row, _, _ in pending:
        per_message[row.msg_id] = per_message.get(row.msg_id, 0) + 1
    holdout = _holdout_message_ids(per_message)
    items = [
        {
            "item_id": f"{row.msg_id}:{question_id}",
            "msg_id": row.msg_id,
            "question_id": question_id,
            "state": row.message,
            "question": definitions[question_id],
            "target_option": target,
            "role": ROLE_HOLDOUT if row.msg_id in holdout else ROLE_TRAIN,
        }
        for row, question_id, target in pending
    ]
    return items, excluded


def _jsonl(items: Sequence[dict]) -> bytes:
    # Not sorted: option order inside a question is positional in Laya, and sorting the keys would
    # reorder the criteria. Key order is fixed where each item is built, so the output is stable.
    lines = (json.dumps(item, ensure_ascii=False) for item in items)
    return ("\n".join(lines) + "\n").encode("utf-8")


def build_manifest(
    items: Sequence[dict],
    rows: Sequence[MessageRow],
    excluded: dict[str, int],
    guard: GuardResult,
    *,
    input_sha256: str,
    items_sha256: str,
    set_version: str,
    exporter_git_sha: str,
) -> dict:
    """The manifest copied into the run record: hashes, counts, exclusions and guard results."""
    definitions = question_definitions()
    counts = {
        question_id: {
            option: sum(
                1
                for item in items
                if item["question_id"] == question_id and item["target_option"] == option
            )
            for option in definition["criteria"]
        }
        for question_id, definition in definitions.items()
    }
    reviewed = sum(1 for row in rows if row.provenance.review_verdict in _REVIEWED)
    return {
        "exporter_version": EXPORTER_VERSION,
        "exporter_git_sha": exporter_git_sha,
        "input_sha256": input_sha256,
        "items_sha256": items_sha256,
        "set_version": set_version,
        # A set version fixes its rubric version (TSD-019): v1/ is gold/rubric-v1.md.
        "rubric_version": set_version,
        "question_schema_sha256": question_schema_sha256(),
        "counts": counts,
        "roles": {
            role: sum(1 for item in items if item["role"] == role)
            for role in (ROLE_TRAIN, ROLE_HOLDOUT)
        },
        "reviewed": reviewed,
        "unreviewed": len(rows) - reviewed,
        "excluded": dict(sorted(excluded.items())),
        "leakage_guard": [{"check": c.check, "passed": c.passed} for c in guard.checks],
    }


def export_train_split(inputs: GuardInputs, out_dir: str | Path, exporter_git_sha: str) -> dict:
    """Write ``items.jsonl`` and ``manifest.json``; raise ``LeakageError`` and write nothing if
    the guard fails. Returns the manifest.

    Rows whose review verdict is ``fail`` are removed from the split (TSD-019 P4) and counted,
    before the guard runs. Existing output files are never overwritten.
    """
    kept = [row for row in inputs.train if row.provenance.review_verdict != "fail"]
    failed = len(inputs.train) - len(kept)
    guard = run_leakage_guard(replace(inputs, train=kept))
    if not guard.passed:
        raise LeakageError(guard)
    items, excluded = build_items(kept)
    if failed:
        excluded["review verdict fail (removed from the split)"] = failed
    items_bytes = _jsonl(items)
    manifest = build_manifest(
        items,
        kept,
        excluded,
        guard,
        input_sha256=inputs.messages_sha256,
        items_sha256=hashlib.sha256(items_bytes).hexdigest(),
        set_version=inputs.set_version,
        exporter_git_sha=exporter_git_sha,
    )
    directory = Path(out_dir)
    targets = (directory / "items.jsonl", directory / "manifest.json")
    for path in targets:
        if path.exists():
            raise FileExistsError(f"{path} already exists; an export is never overwritten")
    directory.mkdir(parents=True, exist_ok=True)
    targets[0].write_bytes(items_bytes)
    targets[1].write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def _optional_rows(path: Path) -> list[MessageRow] | None:
    return load_message_rows(path)[0] if path.is_file() else None


def _optional_seeds(path: Path) -> list[SeedRow] | None:
    return load_seed_registry(path) if path.is_file() else None


def _id_text_pairs(directory: Path | None) -> list[tuple[str, str]]:
    """``(id, message)`` pairs from every ``*.jsonl`` file in a directory (none if it is absent)."""
    pairs: list[tuple[str, str]] = []
    if directory is not None and directory.is_dir():
        for path in sorted(directory.glob("*.jsonl")):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if line.strip():
                    data = json.loads(line)
                    pairs.append(
                        (str(data.get("msg_id", f"{path.name}:{number}")), data["message"])
                    )
    return pairs


def load_guard_inputs(
    *,
    set_dir: Path,
    train_path: Path | None = None,
    gold_path: Path,
    eval_messages: Sequence[tuple[str, str]],
    portuguese_dir: Path | None = None,
) -> GuardInputs:
    """Read everything the guard compares against. A file that is missing becomes ``None`` for the
    comparison sets, which the guard fails closed on."""
    train_file = train_path or set_dir / "train.jsonl"
    train, non_spanish = load_message_rows(train_file)
    gold = [
        GoldRecord.model_validate_json(line)
        for line in gold_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return GuardInputs(
        train=train,
        train_seeds=_optional_seeds(set_dir / "seeds.train.jsonl") or [],
        set_version=set_dir.name,
        messages_sha256=hashlib.sha256(train_file.read_bytes()).hexdigest(),
        acceptance=load_acceptance(set_dir / "acceptance.json"),
        calibration=_optional_rows(set_dir / "calibration.jsonl"),
        test=_optional_rows(set_dir / "test.jsonl"),
        calibration_seeds=_optional_seeds(set_dir / "seeds.calibration.jsonl"),
        test_seeds=_optional_seeds(set_dir / "seeds.test.jsonl"),
        gold=gold,
        eval_messages=list(eval_messages),
        portuguese_messages=_id_text_pairs(portuguese_dir),
        non_spanish_train_ids=non_spanish,
    )
