"""Generation briefs for the team-generated message set (TSD-019, T-106).

A brief says what one drafted message is *for*: the intent, the persona
voice and, in the test supplement, the adversarial kind. It is derived
from the committed seed registry and the P1 composition only, so the same
registry always gives the same briefs and no key, record or LLM is
involved. Quotas are never silently filled with other kinds (P2): a cell
the registry cannot supply is reported as a shortfall and the seeds left
over get no brief.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass, field

from calvino.data.message_set import BRIEF_DEFAULTS, SeedRow

COUNTRIES = ("MX", "CO", "AR")

# (intent, per-variant count, seed kinds in order of preference). Scarce
# kinds are drawn first so a plentiful clean-transaction pool cannot eat
# the complaint seeds the case intents need.
_PLAIN_TRAIN = (
    ("case_status", 25, ("complaint",)),
    ("open_case", 25, ("problem_transaction", "complaint")),
    ("out_of_scope", 10, ("no_record",)),
    ("fraud_report", 10, ("problem_transaction", "clean_transaction")),
    ("dispute", 10, ("clean_transaction", "problem_transaction")),
    ("manipulation", 20, ("no_record", "clean_transaction", "problem_transaction")),
    ("explain", 25, ("problem_transaction", "clean_transaction", "other_customer")),
    ("cancel", 25, ("problem_transaction", "clean_transaction", "other_customer")),
    ("retry", 25, ("problem_transaction", "clean_transaction", "other_customer")),
    ("human", 25, ("problem_transaction", "clean_transaction", "other_customer")),
)
# Calibration and the test base slice: 60 stuck + 10 heads + 10 injection.
# Complaint seeds (8 per variant) ground case_status; open_case prefers a
# problem transaction so it cannot starve it. out_of_scope is 2 per variant
# because the registry holds 2 nominal no-record seeds per variant per split.
_PLAIN_EVAL = (
    ("case_status", 10, ("complaint",)),
    ("open_case", 10, ("problem_transaction", "complaint")),
    ("out_of_scope", 2, ("no_record",)),
    ("fraud_report", 4, ("problem_transaction", "clean_transaction")),
    ("dispute", 4, ("clean_transaction", "problem_transaction")),
    ("manipulation", 10, ("no_record", "clean_transaction", "problem_transaction")),
    ("explain", 10, ("problem_transaction", "clean_transaction", "other_customer")),
    ("cancel", 10, ("problem_transaction", "clean_transaction", "other_customer")),
    ("retry", 10, ("problem_transaction", "clean_transaction", "other_customer")),
    ("human", 10, ("problem_transaction", "clean_transaction", "other_customer")),
)
QUOTAS = {"train": _PLAIN_TRAIN, "calibration": _PLAIN_EVAL, "test": _PLAIN_EVAL}

# Test supplement, ~40 rewordings in total (P1).
REWORDING_QUOTA = (
    ("wrong_data", 5),
    ("missing_data", 5),
    ("injection", 10),
    ("multilingual", 8),
    ("edge", 12),
)
EDGE_KINDS = ("exchange_rate", "hostile_tone", "empty", "emoji_only", "garbled")
# Edge kinds with no recognisable request: in-workflow but unclassifiable.
UNCLASSIFIABLE_EDGE = ("empty", "emoji_only", "garbled")

PERSONA_VOICES = (
    "terse, calm",
    "detailed, calm",
    "terse, worried",
    "detailed, worried",
    "polite, in a hurry",
    "casual, slightly annoyed",
)


@dataclass
class BriefReport:
    """Briefs built plus every quota the registry could not fill."""

    briefs: list[dict] = field(default_factory=list)
    shortfalls: list[str] = field(default_factory=list)
    unassigned: int = 0


def _order_key(seed: SeedRow) -> str:
    """Deterministic, registry-order-independent ordering of a seed pool."""
    return hashlib.sha256(seed.seed_key.encode("utf-8")).hexdigest()


def _voice(seed: SeedRow) -> str:
    digest = hashlib.sha256(b"voice|" + seed.seed_key.encode("utf-8")).digest()
    return PERSONA_VOICES[digest[0] % len(PERSONA_VOICES)]


def build_plain_briefs(split: str, seeds: Iterable[SeedRow]) -> BriefReport:
    """Briefs for the base slice: per country variant, draw each intent's
    quota from its preferred seed kinds, scarce intents first."""
    report = BriefReport()
    base = [seed for seed in seeds if seed.kind not in ("rewording", "hand_written")]
    for country in COUNTRIES:
        pools: dict[str, list[SeedRow]] = {}
        for seed in sorted((s for s in base if s.country_variant == country), key=_order_key):
            pools.setdefault(seed.kind, []).append(seed)
        deficit = 0
        for intent, count, kinds in QUOTAS[split]:
            if intent == "open_case":
                # Slots case_status could not fill (a thin complaint pool)
                # go to open_case, grounded by a problem transaction.
                count += deficit
            drawn = 0
            for kind in kinds:
                pool = pools.get(kind, [])
                while pool and drawn < count:
                    seed = pool.pop(0)
                    report.briefs.append(
                        {
                            "seed_key": seed.seed_key,
                            "intent": intent,
                            "persona_voice": _voice(seed),
                        }
                    )
                    drawn += 1
            if drawn < count:
                if intent == "case_status":
                    deficit = count - drawn
                    report.shortfalls.append(
                        f"{split}/{country}/{intent}: {drawn} of {count}; "
                        f"{deficit} reassigned to open_case (complaint seeds are the limit)"
                    )
                else:
                    report.shortfalls.append(
                        f"{split}/{country}/{intent}: {drawn} of {count} "
                        f"(needs {' or '.join(kinds)} seeds)"
                    )
        report.unassigned += sum(len(pool) for pool in pools.values())
    return report


def build_rewording_briefs(
    seeds: Iterable[SeedRow],
    parent_briefs: dict[str, dict],
    parent_messages: dict[str, str] | None = None,
) -> BriefReport:
    """Briefs for the test supplement: each rewording keeps its parent's
    intent (injection becomes ``manipulation``; empty, emoji-only and
    garbled edges become ``none``), under one adversarial kind."""
    report = BriefReport()
    rewordings = sorted((s for s in seeds if s.kind == "rewording"), key=_order_key)
    kinds = [kind for kind, count in REWORDING_QUOTA for _ in range(count)]
    edge_cycle = 0
    for index, seed in enumerate(rewordings):
        parent = parent_briefs.get(seed.parent_seed_key or "")
        if parent is None:
            report.shortfalls.append(f"rewording {seed.seed_key}: parent brief not found")
            report.unassigned += 1
            continue
        if index >= len(kinds):
            report.unassigned += 1
            continue
        kind = kinds[index]
        intent = parent["intent"]
        brief: dict = {
            "seed_key": seed.seed_key,
            "adversarial_kind": kind,
            "persona_voice": _voice(seed),
        }
        if kind == "injection":
            intent = "manipulation"
        elif kind == "edge":
            edge_kind = EDGE_KINDS[edge_cycle % len(EDGE_KINDS)]
            edge_cycle += 1
            brief["edge_kind"] = edge_kind
            if edge_kind in UNCLASSIFIABLE_EDGE:
                intent = "none"
        brief["intent"] = intent
        text = (parent_messages or {}).get(seed.parent_seed_key or "")
        if text:
            brief["parent_message"] = text
        report.briefs.append(brief)
    if len(rewordings) < len(kinds):
        report.shortfalls.append(
            f"test/rewordings: {len(rewordings)} of {len(kinds)} supplement seeds in the registry"
        )
    return report


def validate_briefs(briefs: Iterable[dict]) -> list[str]:
    """Every intent must be one the derivation table knows."""
    problems = []
    for brief in briefs:
        if brief["intent"] not in BRIEF_DEFAULTS:
            problems.append(f"{brief['seed_key']}: unknown intent {brief['intent']!r}")
    return problems


__all__ = [
    "BriefReport",
    "build_plain_briefs",
    "build_rewording_briefs",
    "validate_briefs",
]
