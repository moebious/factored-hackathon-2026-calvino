"""Committed registry writer: facts-only rows with salted keys (TSD-019 P3, T-106).

Committed registries carry seed *facts*, never records: no real customer
ids, no transcript text, no complaint text. Customer identity is stored as
a truncated salted hash (enough for the L1 equality check, not enough to
identify anyone). The salt is secret and per set version: it lives in the
git-ignored ``data/message-set-salt-v1`` and is passed in here, never
written. The datasheet records the salt version only, never the value.

The full seed_key to record pointer log is git-ignored too
(``data/message-set-seed-log.jsonl``): ``write_pointer_log`` refuses any
path git would commit and fails closed when git cannot answer, mirroring
the fail-closed check in ``scripts/generate_message_set.py`` (this package
cannot import that script, so the ten-line guard is repeated, not shared).
Losing the salt or the pointer log means the set cannot be regenerated,
which the datasheet states.

Every test here runs offline on synthetic fixtures: no network, no keys,
no dataset. The salt in tests is a fixed non-secret string.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from calvino.data.message_set import (
    SALT_VERSION,
    SET_VERSION,
    SeedRow,
    derive_seed_key,
    salted_customer_hash,
)
from calvino.data.seed_pull import DrawnSeed, SeedCandidate, band_for

DEFAULT_PROMPT_IDS = {"train": "train-v1", "calibration": "train-v1", "test": "test-v1"}


@dataclass(frozen=True)
class PointerEntry:
    """One git-ignored pointer: the record behind a committed seed row."""

    seed_key: str
    set_version: str
    salt_version: str
    split: str
    kind: str
    record_id: str
    role: str
    customer_id: str
    customer_hash: str


def is_git_ignored(path: Path) -> bool:
    """Whether git would ignore this path. Fail closed: any git error
    means not ignored, so the pointer log is never written on a guess."""
    try:
        return (
            subprocess.run(
                ["git", "check-ignore", "-q", str(path)],
                check=False,
                capture_output=True,
            ).returncode
            == 0
        )
    except OSError:
        return False


def build_registry(
    drawn: list[DrawnSeed],
    *,
    salt: str,
    set_version: str = SET_VERSION,
    policy_version: str,
    gate_limits: dict[str, float],
    prompt_ids: dict[str, str] | None = None,
) -> tuple[list[SeedRow], list[PointerEntry]]:
    """Turn drawn seeds into committed rows plus git-ignored pointers.

    Keys and hashes are derived under the per-version secret salt; the
    returned rows validate as ``SeedRow`` and carry no raw record or
    customer ids. Rewordings are never built here (fresh keys with
    ``parent_seed_key`` come from test seeds at generation time);
    nominal no-record rows use ``nominal_seed`` below.
    """
    prompts = prompt_ids or dict(DEFAULT_PROMPT_IDS)
    seeds: list[SeedRow] = []
    pointers: list[PointerEntry] = []
    for item in drawn:
        candidate = item.candidate
        seed_key = derive_seed_key(
            salt=salt,
            set_version=set_version,
            split=item.split,
            kind=item.kind,
            record_id=candidate.record_id,
        )
        customer_hash = salted_customer_hash(candidate.customer_id, salt)
        band = band_for(candidate, gate_limits)
        currency = candidate.currency
        seeds.append(
            SeedRow.model_validate(
                {
                    "seed_key": seed_key,
                    "split": item.split,
                    "prompt_id": prompts[item.split],
                    "kind": item.kind,
                    "customer_hash": customer_hash,
                    "country_variant": candidate.country_variant,
                    "record_facts": {
                        "kind": item.kind,
                        "status": candidate.status,
                        "transaction_type": candidate.transaction_type,
                        "amount": candidate.amount,
                        "amount_band": band,
                        "currency": currency,
                        "fraud_flag": candidate.fraud_flag,
                        "channel": candidate.channel,
                        "complaint_status": candidate.complaint_status,
                        "sla_state": candidate.sla_state,
                    },
                    "event_date": candidate.event_date.isoformat(),
                    "policy_version": policy_version,
                    "gate_limit_used": gate_limits[currency]
                    if band is not None and currency
                    else None,
                }
            )
        )
        pointers.append(
            PointerEntry(
                seed_key=seed_key,
                set_version=set_version,
                salt_version=SALT_VERSION,
                split=item.split,
                kind=item.kind,
                record_id=candidate.record_id,
                role="base",
                customer_id=candidate.customer_id,
                customer_hash=customer_hash,
            )
        )
    return seeds, pointers


def nominal_seed(
    *,
    persona_id: str,
    country_variant: str,
    event_date: str,
    salt: str,
    set_version: str = SET_VERSION,
    policy_version: str,
    prompt_id: str = "train-v1",
    split: str = "train",
) -> tuple[SeedRow, PointerEntry]:
    """One nominal no-record seed: the persona id is hashed like a customer
    id, so the committed row carries no pointer to anything real."""
    seed_key = derive_seed_key(
        salt=salt, set_version=set_version, split=split, kind="no_record", record_id=persona_id
    )
    customer_hash = salted_customer_hash(persona_id, salt)
    seed = SeedRow.model_validate(
        {
            "seed_key": seed_key,
            "split": split,
            "prompt_id": prompt_id,
            "kind": "no_record",
            "customer_hash": customer_hash,
            "country_variant": country_variant,
            "record_facts": {"kind": "no_record"},
            "event_date": event_date,
            "policy_version": policy_version,
        }
    )
    pointer = PointerEntry(
        seed_key=seed_key,
        set_version=set_version,
        salt_version=SALT_VERSION,
        split=split,
        kind="no_record",
        record_id=persona_id,
        role="base",
        customer_id=persona_id,
        customer_hash=customer_hash,
    )
    return seed, pointer


def write_seeds_jsonl(path: Path, seeds: list[SeedRow]) -> int:
    """Write committed registry rows, one JSON object per line."""
    with path.open("w", encoding="utf-8") as handle:
        for seed in seeds:
            handle.write(seed.model_dump_json() + "\n")
    return len(seeds)


def write_pointer_log(path: Path, pointers: list[PointerEntry]) -> int:
    """Append pointer entries to the git-ignored log. Refuses any path git
    would commit: the record pointers are never committed."""
    if not is_git_ignored(path):
        raise SystemExit(f"refusing: pointer log {path} is not git-ignored")
    with path.open("a", encoding="utf-8") as handle:
        for entry in pointers:
            handle.write(json.dumps(entry.__dict__, sort_keys=True) + "\n")
    return len(pointers)


def load_seed_registry(path: Path) -> list[SeedRow]:
    """Parse and validate one committed ``seeds.{split}.jsonl`` file."""
    rows = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if line.strip():
                try:
                    rows.append(SeedRow.model_validate(json.loads(line)))
                except ValueError as error:
                    raise SystemExit(f"{path}:{number}: invalid seed row: {error}") from error
    return rows


def record_ids_from_pointer_log(path: Path) -> dict[str, str]:
    """Map seed_key back to its record id from the git-ignored pointer log.

    The duplicate-draw record check needs this; without the log (CI, which
    never sees it) callers pass ``None`` ids and keep the seed-key check.
    """
    mapping = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                entry = json.loads(line)
                mapping[entry["seed_key"]] = entry["record_id"]
    return mapping


def candidate_from_pointer(
    entry: PointerEntry,
    *,
    event_date: str = "2024-03-10",
) -> SeedCandidate:
    """Rebuild a draw-time candidate shell from a pointer entry (offline).

    Facts stay in the committed row; this carries only the pointers the
    sampler needs, for regeneration checks given the salt and the log.
    """
    return SeedCandidate(
        record_id=entry.record_id,
        customer_id=entry.customer_id,
        event_date=date.fromisoformat(event_date),
        kind=entry.kind,
        country_variant="MX",
    )
