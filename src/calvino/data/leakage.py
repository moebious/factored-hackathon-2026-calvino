"""The five leakage rules (TSD-015, T-103).

Each ``check_*`` returns a list of violations; an empty list passes. T-106
references these rules by id and runs them over its seed registries; here
they are worded and tested on synthetic fixtures only.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime

from calvino.data.splits import CALIBRATION_START, TEST_START


@dataclass(frozen=True)
class Violation:
    """One breached leakage rule, with the offending key for the report."""

    rule_id: str
    detail: str


@dataclass(frozen=True)
class CandidateInput:
    """One built classifier input: its text and the source it came through."""

    text: str
    source: str


@dataclass(frozen=True)
class SeedEntry:
    """One row of a message-generation seed registry (T-106 executes this)."""

    seed_key: str
    split: str
    prompt_id: str


def check_l1_customer_isolation(assignments: Mapping[str, set[str]]) -> list[Violation]:
    """L1: no customer_id appears in more than one split (train, calibration,
    test or gold)."""
    seen: dict[str, str] = {}
    violations: list[Violation] = []
    for split in sorted(assignments):
        for customer_id in sorted(assignments[split]):
            if customer_id in seen:
                violations.append(
                    Violation(
                        "L1",
                        f"{customer_id} in both {seen[customer_id]} and {split}",
                    )
                )
            else:
                seen[customer_id] = split
    return violations


def check_l2_time_order(records: list[tuple[str, date | datetime]]) -> list[Violation]:
    """L2: no train record at/after the calibration start; no train or
    calibration record at/after the test start."""
    violations: list[Violation] = []
    for index, (split, event_date) in enumerate(records):
        day = event_date.date() if isinstance(event_date, datetime) else event_date
        if split == "train" and day >= CALIBRATION_START:
            violations.append(Violation("L2", f"record {index} trains on {day}"))
        if split in ("train", "calibration") and day >= TEST_START:
            violations.append(Violation("L2", f"record {index} ({split}) sees {day}"))
    return violations


def check_l3_dataset_text(
    candidates: list[CandidateInput],
    template_texts: set[str],
    team_sources: set[str],
) -> list[Violation]:
    """L3: no dataset template text in any classifier input; message text may
    only enter through team-generated sources. ``template_texts`` stands in
    for the 42 transcript templates and 5 complaint texts at implementation;
    T-106 passes the real sets."""
    normalised = {t.strip() for t in template_texts}
    violations: list[Violation] = []
    for index, candidate in enumerate(candidates):
        if candidate.source not in team_sources:
            violations.append(Violation("L3", f"input {index} via {candidate.source}"))
        if candidate.text.strip() in normalised:
            violations.append(Violation("L3", f"input {index} copies dataset text"))
    return violations


def check_l4_generation_isolation(entries: list[SeedEntry]) -> list[Violation]:
    """L4: train and test messages come from disjoint seed-record sets under
    separate prompts; no seed key feeds both sides."""
    train_keys = {e.seed_key for e in entries if e.split == "train"}
    test_keys = {e.seed_key for e in entries if e.split == "test"}
    shared = sorted(train_keys & test_keys)
    return [Violation("L4", f"seed {key} feeds train and test") for key in shared]


def check_l5_gold_held_out(
    gold_customers: set[str],
    gold_seeds: set[str],
    train_keys: set[str],
    calibration_keys: set[str],
) -> list[Violation]:
    """L5: gold customer and seed keys stay out of train and calibration;
    gold is for oracle/judge agreement and final reporting only."""
    violations: list[Violation] = []
    for key in sorted(gold_customers & train_keys):
        violations.append(Violation("L5", f"gold customer {key} trains"))
    for key in sorted(gold_customers & calibration_keys):
        violations.append(Violation("L5", f"gold customer {key} calibrates"))
    for key in sorted(gold_seeds & train_keys):
        violations.append(Violation("L5", f"gold seed {key} trains"))
    for key in sorted(gold_seeds & calibration_keys):
        violations.append(Violation("L5", f"gold seed {key} calibrates"))
    return violations
