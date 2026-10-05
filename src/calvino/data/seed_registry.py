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
import os
import secrets
import stat
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from calvino.data.message_set import (
    SALT_VERSION,
    SET_VERSION,
    MessageLabels,
    MessageOracleFacts,
    RegistryCheckReport,
    SeedRow,
    derive_defaults,
    derive_seed_key,
    gate_table_hash,
    run_registry_checks,
    salted_customer_hash,
    seed_to_oracle_facts,
)
from calvino.data.seed_pull import DrawnSeed, SeedCandidate, band_for
from calvino.evaluation.oracle import oracle_outcome

DEFAULT_PROMPT_IDS = {"train": "train-v1", "calibration": "train-v1", "test": "test-v1"}

# Grow-vs-displace rule for nominal no-record seeds (population procedure
# is documented in the message-set datasheet; needs a one-line TSD-019
# amendment at review): nominals fill ONLY their own quota cell
# (NO_RECORD_NOMINAL in seed_pull) and are appended after the
# record-backed draws. They never backfill a record-backed shortfall --
# a short record cell raises SeedShortfall instead -- and record-backed
# draws never displace nominals. "False" means nominals do not grow the
# committed total beyond its quota cell either: the committed total is
# drawn quota plus nominal quota, nothing more.
NO_RECORD_BACKFILLS_SHORTFALLS = False

# Nominal event dates for no-record rows: one fixed date per split window
# (train / calibration / test), so nominal rows carry a date without
# pointing at any record. Persona ids are synthetic and deterministic
# per (split, variant, index).
NOMINAL_EVENT_DATES = {"train": "2024-03-10", "calibration": "2025-08-10", "test": "2026-02-10"}


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


def ensure_salt(path: Path) -> str:
    """Load the per-version secret salt, creating it once with owner-only
    permissions. Refuses any path git would commit: the salt is never
    committed."""
    if not is_git_ignored(path):
        raise SystemExit(f"refusing: salt file {path} is not git-ignored")
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    value = secrets.token_hex(32)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(value + "\n")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise SystemExit(f"refusing: salt file {path} is group/world readable")
    print(f"created per-version salt at {path} (secret, git-ignored)")
    return value


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
        # De-identified by construction: the raw amount never leaves the
        # pull (bands only) and no gate limit is echoed back; the table
        # hash lets the oracle path verify the band's table without one.
        # Residual risk, stated once: event_date + currency + channel +
        # type stays, and a rare combination could still single out a row.
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
                        "amount_band": band,
                        "currency": currency,
                        "fraud_flag": candidate.fraud_flag,
                        "channel": candidate.channel,
                        "complaint_status": candidate.complaint_status,
                        "sla_state": candidate.sla_state,
                    },
                    "event_date": candidate.event_date.isoformat(),
                    "policy_version": policy_version,
                    "gate_table_hash": gate_table_hash(gate_limits) if band is not None else None,
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


def build_nominal_seeds(
    split: str,
    count: int,
    *,
    salt: str,
    set_version: str = SET_VERSION,
    policy_version: str,
    prompt_id: str | None = None,
    persona_prefix: str = "persona",
) -> tuple[list[SeedRow], list[PointerEntry]]:
    """Build nominal no-record seeds for one split's quota cell.

    Persona ids are synthetic (``{prefix}-{split}-{variant}-{index}``) and
    deterministic, spread evenly across variants. The committed rows carry
    no amount and no band; see ``nominal_seed``. Asserts the
    grow-vs-displace rule: nominals only ever fill their own cell.
    """
    assert NO_RECORD_BACKFILLS_SHORTFALLS is False, "nominals must never backfill draws"
    prompt = prompt_id or DEFAULT_PROMPT_IDS[split]
    variants = ("MX", "CO", "AR")
    seeds: list[SeedRow] = []
    pointers: list[PointerEntry] = []
    for index in range(count):
        variant = variants[index % len(variants)]
        seed, pointer = nominal_seed(
            persona_id=f"{persona_prefix}-{split}-{variant.lower()}-{index:03d}",
            country_variant=variant,
            event_date=NOMINAL_EVENT_DATES[split],
            salt=salt,
            set_version=set_version,
            policy_version=policy_version,
            prompt_id=prompt,
            split=split,  # type: ignore[arg-type]
        )
        seeds.append(seed)
        pointers.append(pointer)
    return seeds, pointers


def write_seeds_jsonl(path: Path, seeds: list[SeedRow]) -> int:
    """Write committed registry rows, one JSON object per line."""
    with path.open("w", encoding="utf-8") as handle:
        for seed in seeds:
            handle.write(seed.model_dump_json() + "\n")
    return len(seeds)


def write_pointer_log(path: Path, pointers: list[PointerEntry]) -> int:
    """Truncate-write pointer entries to the git-ignored log, owner-only.

    Refuses any path git would commit: the record pointers are never
    committed. The log opens in write mode (never append, so a re-pull
    cannot duplicate keys) and lands at 0600.
    """
    if not is_git_ignored(path):
        raise SystemExit(f"refusing: pointer log {path} is not git-ignored")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for entry in pointers:
            handle.write(json.dumps(entry.__dict__, sort_keys=True) + "\n")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return len(pointers)


def commit_pull_outputs(
    seeds_dir: Path,
    pointer_log: Path,
    rows_by_split: dict[str, list[SeedRow]],
    pointers: list[PointerEntry],
) -> dict[str, int]:
    """Commit one pull: the pointer log first, the registries second.

    The git-ignored log lands (truncated, owner-only) BEFORE any
    registry file is touched: if its guard refuses, the pull aborts
    with no registry written, so a committed row always has its
    pointer. Registries follow, one ``seeds.{split}.jsonl`` per split.
    """
    write_pointer_log(pointer_log, pointers)
    seeds_dir.mkdir(parents=True, exist_ok=True)
    return {
        split: write_seeds_jsonl(seeds_dir / f"seeds.{split}.jsonl", rows)
        for split, rows in rows_by_split.items()
    }


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


@dataclass(frozen=True)
class BridgedRow:
    """One registry row run to its expected outcome: labels, oracle inputs
    and the derived outcome name (derived at load time, never stored)."""

    seed_key: str
    split: str
    reviewed: bool
    labels: MessageLabels
    oracle_facts: MessageOracleFacts
    outcome: str


def bridge_registry_to_oracle(
    seeds: list[SeedRow],
    briefs: dict[str, dict],
    *,
    gate_limits: dict[str, float],
) -> list[BridgedRow]:
    """Run registry rows through the brief table to oracle outcomes.

    Unreviewed rows take the deterministic brief-derived defaults, so the
    oracle is defined on every row with no review (the audit regression:
    rows outside the review sample keep defaults, review only moves a
    field to a logged correction). Reviewed rows (``brief["reviewed"]``)
    carry their corrected ``labels``/``oracle_facts``. A missing brief
    fails loudly: every row needs its intent. The P6 policy-version guard
    runs on this path (``gate_limits`` required), as bands feed the oracle.
    """
    bridged = []
    for seed in seeds:
        brief = briefs.get(seed.seed_key)
        if brief is None:
            raise KeyError(f"no brief for seed {seed.seed_key}: every row needs its intent")
        reviewed = bool(brief.get("reviewed", False))
        if reviewed:
            labels = MessageLabels.model_validate(brief["labels"])
            facts = MessageOracleFacts.model_validate(brief["oracle_facts"])
        else:
            labels, facts = derive_defaults(
                brief_intent=brief["intent"],
                adversarial_kind=brief.get("adversarial_kind"),
                seed_kind=seed.kind,
            )
        labels.validate_area_for_intent(facts.intent)
        oracle_facts = seed_to_oracle_facts(seed, labels, facts, gate_limits=gate_limits)
        bridged.append(
            BridgedRow(
                seed_key=seed.seed_key,
                split=seed.split,
                reviewed=reviewed,
                labels=labels,
                oracle_facts=facts,
                outcome=oracle_outcome(oracle_facts).value,
            )
        )
    return bridged


def run_checks_from_files(
    seed_paths: dict[str, Path],
    message_paths: dict[str, Path] | None = None,
    *,
    record_ids: dict[str, str] | None = None,
    gold_hashes: set[str] | None = None,
    gold_keys: set[str] | None = None,
    gold_texts: list[str] | None = None,
    t303_texts: list[str] | None = None,
    template_texts: set[str] | None = None,
) -> RegistryCheckReport:
    """L1-L5 plus the TSD-019 scans over committed registry files, by id.

    Wiring only: loads ``seeds.{split}.jsonl`` (and optional message
    files), keys everything by ``seed_key``/``customer_hash``, and runs
    ``run_registry_checks``. Real registries come later; until then this
    runs on synthetic fixtures. Without the git-ignored pointer log the
    record-id redraw check degrades to seed-key uniqueness (stated in the
    report notes); pass ``record_ids`` from ``record_ids_from_pointer_log``
    for the full duplicate-draw check.
    """
    from calvino.data.message_set import MessageRow  # noqa: PLC0415

    seeds = {split: load_seed_registry(path) for split, path in seed_paths.items()}
    messages: dict[str, list[MessageRow]] = {}
    for split, path in (message_paths or {}).items():
        rows = []
        with path.open(encoding="utf-8") as handle:
            for number, line in enumerate(handle, 1):
                if line.strip():
                    try:
                        rows.append(MessageRow.model_validate(json.loads(line)))
                    except ValueError as error:
                        raise SystemExit(
                            f"{path}:{number}: invalid message row: {error}"
                        ) from error
        messages[split] = rows
    ids = {
        split: [(record_ids or {}).get(seed.seed_key) for seed in rows]
        for split, rows in seeds.items()
    }
    report = run_registry_checks(
        seeds=seeds,
        messages=messages,
        record_ids=ids,
        gold_hashes=gold_hashes or set(),
        gold_keys=gold_keys or set(),
        gold_texts=gold_texts or [],
        t303_texts=t303_texts or [],
        template_texts=template_texts or set(),
    )
    if record_ids is None:
        report.notes.append(
            "record-id redraw check degraded to seed-key uniqueness: no pointer log given"
        )
    return report
