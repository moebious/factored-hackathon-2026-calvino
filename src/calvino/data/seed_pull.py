"""P2 seed sourcing: filter-first sampling over a lakehouse-shaped input (TSD-019, T-106).

A candidate record is usable only when its customer bucket *and* its event
date agree on one split (the TSD-015 AND-condition in
``calvino.data.splits``). This module filters to usable records first, then
samples to the P1 composition -- there is no fixed oversample factor to
hit. The pull report states considered, usable, drawn and excluded counts
per split, so any roughly twofold considered-to-drawn pull is visible as
accounting, never as a target.

Live reads stay in ``calvino.data.inventory_access`` (the only module that
touches the dataset): this module reads lakehouse-shaped rows through the
``LakehouseSource`` interface, so every test runs on synthetic fixtures
with no network, no keys, no dataset and no salt.

Sampling notes (all unit-tested on fixtures):

- Calibration and test pools are thin, so usable records are counted per
  seed kind before drafting and complaint-seed tightness is flagged in the
  report: quotas are never silently filled with other kinds.
- Variants are balanced evenly (MX/CO/AR); a short variant pool is topped
  up from the others and the top-up is noted, never silent.
- Within each (split, variant) pool the draw is uniform random under a
  fixed seed, so the natural outcome mix is preserved by construction;
  the report states the pool mix and the drawn mix side by side.
- Transaction amounts avoid the P6 margins (within ±20% of a gate limit,
  within 20% below or anywhere above the hard-rule limit): those rows are
  excluded before sampling, never forced into a split.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Protocol

from calvino.data.labels import PROBLEM_TRANSACTION_STATUSES
from calvino.data.message_set import amount_band_for, usable_amount
from calvino.data.splits import assign_customer, assign_record

SET_VERSION = "v1"

VARIANTS = ("MX", "CO", "AR")

COUNTRY_BY_CUSTOMER_COUNTRY = {"México": "MX", "Colombia": "CO", "Argentina": "AR"}

# P1 base quotas: seed-generated rows only (train 600, calibration 240,
# test 240). The ~60-case test supplement (adversarial rewordings of test
# seeds plus hand-written rows) is drawn from test-split seeds only and is
# never pulled here.
BASE_QUOTAS = {"train": 600, "calibration": 240, "test": 240}

# Complaint floors that keep the open-a-case / case-status intents grounded
# (10% of each base quota, a sampler default, not a spec figure): usable
# complaint counts below these flag tightness in the report.
COMPLAINT_FLOORS = {"train": 60, "calibration": 24, "test": 24}

# Share of drawn transaction seeds re-roled as other-customer access probes
# (a sampler default; the role is assigned at draw time from usable records
# of the same split, never across splits).
OTHER_CUSTOMER_SHARE = 0.05

# Complaint rows outside this category never ground case intents.
COMPLAINT_CATEGORY = "Transactions"


class LakehouseSource(Protocol):
    """Lakehouse-shaped rows behind an interface: no S3, no credentials.

    Each method yields plain mappings shaped like the ``calvino.data``
    contracts (customers carry ``customer_id``/``country``; transactions
    carry ``transaction_id``/``customer_id``/``transaction_date``/``status``
    fields; complaints carry ``complaint_id``/``customer_id``/
    ``creation_date``). The live implementation loads these with
    ``inventory_access``; tests use a fake.
    """

    def iter_customers(self) -> Iterable[Mapping[str, object]]: ...
    def iter_transactions(self) -> Iterable[Mapping[str, object]]: ...
    def iter_complaints(self) -> Iterable[Mapping[str, object]]: ...


@dataclass(frozen=True)
class SeedCandidate:
    """One record-backed seed candidate: pointers live here only, until the
    writer turns them into salted hashes and a git-ignored pointer log."""

    record_id: str
    customer_id: str
    event_date: date
    kind: str  # problem_transaction | clean_transaction | complaint
    country_variant: str  # MX | CO | AR
    status: str | None = None
    transaction_type: str | None = None
    amount: float | None = None
    currency: str | None = None
    fraud_flag: bool = False
    channel: str | None = None
    complaint_status: str | None = None
    sla_state: str | None = None


@dataclass(frozen=True)
class DrawnSeed:
    """One sampled seed with its final kind (some transaction draws are
    re-roled as other-customer access probes of the same split)."""

    candidate: SeedCandidate
    split: str
    kind: str


@dataclass
class SplitPullReport:
    """Considered, usable, drawn and excluded counts per split (P2), plus
    the pool-vs-drawn outcome mix and the complaint-tightness flag."""

    considered: dict[str, int] = field(default_factory=dict)
    usable: dict[str, int] = field(default_factory=dict)
    drawn: dict[str, int] = field(default_factory=dict)
    excluded: dict[str, int] = field(default_factory=dict)
    usable_complaints: dict[str, int] = field(default_factory=dict)
    complaint_tight: dict[str, bool] = field(default_factory=dict)
    pool_status_mix: dict[str, dict[str, int]] = field(default_factory=dict)
    drawn_status_mix: dict[str, dict[str, int]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def _event_day(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def candidates_from_lakehouse(
    source: LakehouseSource,
) -> tuple[list[SeedCandidate], dict[str, int]]:
    """Map lakehouse rows to record-backed candidates (no sampling yet).

    Returns the candidates and a skipped-row count by reason. Rows with no
    event date, an unknown customer or country, an unexpected status, a
    non-Transactions complaint, or a non-allowlisted currency are skipped
    and counted -- never forced into a split. No-record seeds are nominal
    (built downstream, never pulled), so none appear here.
    """
    variants = {}
    for row in source.iter_customers():
        customer_id = row.get("customer_id")
        variant = COUNTRY_BY_CUSTOMER_COUNTRY.get(row.get("country"))  # type: ignore[arg-type]
        if isinstance(customer_id, str) and customer_id and variant is not None:
            variants[customer_id] = variant

    skipped: Counter[str] = Counter()
    candidates: list[SeedCandidate] = []
    for row in source.iter_transactions():
        record_id = row.get("transaction_id")
        customer_id = row.get("customer_id")
        day = _event_day(row.get("transaction_date"))
        variant = variants.get(customer_id) if isinstance(customer_id, str) else None
        status = row.get("transaction_status")
        if not isinstance(record_id, str) or not record_id:
            skipped["transaction:missing-id"] += 1
            continue
        if day is None:
            skipped["transaction:missing-date"] += 1
            continue
        if variant is None:
            skipped["transaction:unknown-customer-or-country"] += 1
            continue
        if status in PROBLEM_TRANSACTION_STATUSES:
            kind = "problem_transaction"
        elif status == "Approved":
            kind = "clean_transaction"
        else:
            skipped["transaction:unexpected-status"] += 1
            continue
        currency = row.get("currency")
        if currency is not None and currency not in ("MXN", "COP", "ARS", "USD"):
            skipped["transaction:unexpected-currency"] += 1
            continue
        candidates.append(
            SeedCandidate(
                record_id=record_id,
                customer_id=customer_id,  # type: ignore[arg-type]
                event_date=day,
                kind=kind,
                country_variant=variant,
                status=status,  # type: ignore[arg-type]
                transaction_type=row.get("transaction_type")  # type: ignore[arg-type]
                if isinstance(row.get("transaction_type"), str)
                else None,
                amount=float(row["amount"])
                if isinstance(row.get("amount"), (int, float))
                else None,
                currency=currency,  # type: ignore[arg-type]
                fraud_flag=bool(row.get("is_fraud")),
                channel=row.get("channel")  # type: ignore[arg-type]
                if isinstance(row.get("channel"), str)
                else None,
            )
        )
    for row in source.iter_complaints():
        record_id = row.get("complaint_id")
        customer_id = row.get("customer_id")
        day = _event_day(row.get("creation_date"))
        variant = variants.get(customer_id) if isinstance(customer_id, str) else None
        if not isinstance(record_id, str) or not record_id:
            skipped["complaint:missing-id"] += 1
            continue
        if day is None:
            skipped["complaint:missing-date"] += 1
            continue
        if variant is None:
            skipped["complaint:unknown-customer-or-country"] += 1
            continue
        if row.get("category") != COMPLAINT_CATEGORY:
            skipped["complaint:outside-category"] += 1
            continue
        breached = row.get("sla_breached")
        candidates.append(
            SeedCandidate(
                record_id=record_id,
                customer_id=customer_id,  # type: ignore[arg-type]
                event_date=day,
                kind="complaint",
                country_variant=variant,
                complaint_status=row.get("status")  # type: ignore[arg-type]
                if isinstance(row.get("status"), str)
                else None,
                sla_state=None
                if breached is None
                else ("breached" if bool(breached) else "within_sla"),
            )
        )
    return candidates, dict(skipped)


def pull_seeds(
    candidates: list[SeedCandidate],
    *,
    quotas: dict[str, int] | None = None,
    gate: dict[str, float],
    hard: dict[str, float],
    rng_seed: int = 20261005,
) -> tuple[dict[str, list[DrawnSeed]], SplitPullReport]:
    """Filter to usable records first, then sample to the P1 composition.

    Usability is the AND-condition (bucket and date agree) plus the P6
    amount margins for transaction rows with an amount. Excluded rows are
    attributed to their customer-bucket split, so the report states
    considered, usable, drawn and excluded counts per split. Shortfalls are
    drawn short and noted -- quotas are never silently filled with other
    kinds. Deterministic in ``rng_seed``: the same inputs always draw the
    same seeds.
    """
    wanted = quotas or dict(BASE_QUOTAS)
    report = SplitPullReport()
    usable: dict[str, list[SeedCandidate]] = {"train": [], "calibration": [], "test": []}
    for candidate in candidates:
        report.considered[assign_customer(candidate.customer_id)] = (
            report.considered.get(assign_customer(candidate.customer_id), 0) + 1
        )
        split = assign_record(candidate.customer_id, candidate.event_date)
        if split is None:
            report.excluded[assign_customer(candidate.customer_id)] = (
                report.excluded.get(assign_customer(candidate.customer_id), 0) + 1
            )
            continue
        if (
            candidate.kind in ("problem_transaction", "clean_transaction")
            and candidate.amount is not None
            and candidate.currency is not None
            and not usable_amount(candidate.amount, candidate.currency, gate, hard)
        ):
            report.excluded[split] = report.excluded.get(split, 0) + 1
            continue
        usable[split].append(candidate)
        report.usable[split] = report.usable.get(split, 0) + 1

    rng = random.Random(rng_seed)
    drawn: dict[str, list[DrawnSeed]] = {}
    for split in ("train", "calibration", "test"):
        pool = sorted(usable[split], key=lambda candidate: candidate.record_id)
        report.pool_status_mix[split] = dict(Counter(c.status or c.kind for c in pool))
        report.usable_complaints[split] = sum(1 for c in pool if c.kind == "complaint")
        floor = COMPLAINT_FLOORS[split]
        report.complaint_tight[split] = report.usable_complaints[split] < floor
        if report.complaint_tight[split]:
            report.notes.append(
                f"{split}: only {report.usable_complaints[split]} usable complaint seeds "
                f"(floor {floor}): complaint-seed tightness flagged, quotas not backfilled"
            )
        quota = wanted.get(split, 0)
        by_variant: dict[str, list[SeedCandidate]] = {variant: [] for variant in VARIANTS}
        for candidate in pool:
            by_variant[candidate.country_variant].append(candidate)
        targets = _variant_targets(quota)
        picked: list[SeedCandidate] = []
        for variant in VARIANTS:
            shuffled = by_variant[variant][:]
            rng.shuffle(shuffled)
            picked.extend(shuffled[: targets[variant]])
        if len(picked) < quota:
            # A short variant pool is topped up from the others in fixed
            # variant order; the top-up is noted, never silent.
            remaining = [c for c in pool if c not in picked]
            rng.shuffle(remaining)
            shortfall = min(quota, len(pool)) - len(picked)
            if shortfall > 0:
                picked.extend(remaining[:shortfall])
                report.notes.append(
                    f"{split}: a variant pool ran short, topped up {shortfall} from other variants"
                )
        if len(pool) < quota:
            report.notes.append(
                f"{split}: usable pool {len(pool)} below quota {quota}: drawn short, not backfilled"
            )
        transactions = [c for c in picked if c.kind != "complaint"]
        probes = set(
            rng.sample(transactions, round(OTHER_CUSTOMER_SHARE * len(transactions)))
            if transactions
            else []
        )
        drawn[split] = [
            DrawnSeed(
                candidate=candidate,
                split=split,
                kind="other_customer"
                if candidate in probes and candidate.kind != "complaint"
                else candidate.kind,
            )
            for candidate in picked
        ]
        report.drawn[split] = len(drawn[split])
        report.drawn_status_mix[split] = dict(
            Counter(c.candidate.status or c.candidate.kind for c in drawn[split])
        )
    return drawn, report


def _variant_targets(quota: int) -> dict[str, int]:
    """Split a quota evenly across MX/CO/AR (remainder to MX, then CO)."""
    base, remainder = divmod(quota, len(VARIANTS))
    return {
        variant: base + (1 if index < remainder else 0) for index, variant in enumerate(VARIANTS)
    }


def band_for(candidate: SeedCandidate, gate_limits: dict[str, float]) -> str | None:
    """The P6 amount band for a drawn transaction seed, if it has an amount."""
    if candidate.amount is None or candidate.currency is None:
        return None
    return amount_band_for(candidate.amount, candidate.currency, gate_limits)
