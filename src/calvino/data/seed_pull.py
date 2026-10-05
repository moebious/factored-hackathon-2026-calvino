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

- Per-kind quotas implement the P1 composition (see ``KIND_QUOTAS``):
  quotas are never silently filled with other kinds -- any short cell
  raises ``SeedShortfall`` (fail-closed, counted), including the
  complaint floors, which are enforced on DRAWN counts.
- Stuck-intent seeds are Transfer/Payment problem transactions only;
  other problem types are excluded before sampling (counted, never
  drawn). Brief intents and injection content are assigned at generation
  time; kinds ground them (complaints ground open-a-case/case-status,
  nominal no-record rows ground out-of-scope/empty, clean rows carry
  dispute/fraud-report heads and plain injection positives).
- Each quota cell is split evenly across variants (MX/CO/AR); a short
  variant cell fails closed rather than topping up from other variants,
  so a variant skew is visible as an error, never silent.
- Within each (split, kind, variant) cell the draw is uniform random
  under a fixed seed, so the natural outcome mix is preserved by
  construction; the report states the pool mix and the drawn mix side by
  side, per split and per kind.
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

# P1 composition as per-kind sampler quotas: record-backed draws only
# (train 570, calibration 234, test 234). Nominal no-record rows are
# appended at build time per NO_RECORD_NOMINAL in ``seed_registry``
# (out-of-scope / empty grounding), bringing committed totals to
# 600 / 240 / 240. The ~60-case test supplement (adversarial rewordings
# of test seeds plus hand-written rows) is drawn from test-split seeds
# only and is never pulled here.
#
# Train 570 = 450 stuck-grounding problem transactions (Transfer/Payment
# only, 150/variant) + 60 complaint heads (20/variant) + 60 clean
# carriers for plain injection positives (20/variant). Calibration and
# test 234 = 180 stuck (60/variant at natural status mix) + 24
# complaint heads (8/variant) + 30 clean carriers (10/variant).
KIND_QUOTAS: dict[str, dict[str, int]] = {
    "train": {"problem_transaction": 450, "complaint": 60, "clean_transaction": 60},
    "calibration": {"problem_transaction": 180, "complaint": 24, "clean_transaction": 30},
    "test": {"problem_transaction": 180, "complaint": 24, "clean_transaction": 30},
}

# Nominal no-record rows appended per split at build time (never pulled:
# there is no record behind them). See NO_RECORD_BACKFILLS_SHORTFALLS in
# ``seed_registry`` for the grow-vs-displace rule.
NO_RECORD_NOMINAL = {"train": 30, "calibration": 6, "test": 6}

# Stuck-intent seeds are Transfer/Payment problem transactions only
# (compared case-insensitively; live values are title case). A problem
# transaction of any other type never grounds a stuck intent, so those
# rows are excluded before sampling and counted, never drawn.
STUCK_TRANSACTION_TYPES = ("Transfer", "Payment")

# Allowlisted enums for row-level validation (compared
# case-insensitively; live values observed in the committed registries
# are title case). Unknown values are skipped and counted, never
# coerced: a mistyped feed must fail visibly, not drift into a split.
TRANSACTION_TYPES = ("Transfer", "Payment", "Deposit", "Withdrawal", "Purchase", "Adjustment")
CHANNELS = ("App", "Web", "ATM", "POS", "Branch", "Transfer")
COMPLAINT_STATUSES = ("Open", "In Process", "Resolved", "Closed", "Pending")

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
    the pool-vs-drawn outcome mix and the complaint-tightness flag.

    Floors are fail-closed (``pull_seeds`` raises ``SeedShortfall`` on a
    short cell), so ``complaint_tight`` can only be true on a run that
    raised; it stays in the report so the accounting shape is stable."""

    considered: dict[str, int] = field(default_factory=dict)
    usable: dict[str, int] = field(default_factory=dict)
    drawn: dict[str, int] = field(default_factory=dict)
    excluded: dict[str, int] = field(default_factory=dict)
    usable_complaints: dict[str, int] = field(default_factory=dict)
    complaint_tight: dict[str, bool] = field(default_factory=dict)
    pool_status_mix: dict[str, dict[str, int]] = field(default_factory=dict)
    drawn_status_mix: dict[str, dict[str, int]] = field(default_factory=dict)
    drawn_kinds: dict[str, dict[str, int]] = field(default_factory=dict)
    drawn_variants: dict[str, dict[str, int]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


class SeedShortfall(Exception):
    """Fail-closed quota shortfall: the usable pool cannot meet a quota
    cell, so the pull stops instead of backfilling with other kinds."""


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
    event date, an unknown customer or country, a duplicate record id or
    customer (first-wins), an unexpected status, type, channel or currency,
    a non-Transactions complaint, a missing or unexpected complaint
    status, or a missing fraud/SLA flag are skipped and counted -- never
    forced into a split. No-record seeds are nominal (built downstream,
    never pulled), so none appear here.
    """
    variants = {}
    for row in source.iter_customers():
        customer_id = row.get("customer_id")
        variant = COUNTRY_BY_CUSTOMER_COUNTRY.get(row.get("country"))  # type: ignore[arg-type]
        if isinstance(customer_id, str) and customer_id and variant is not None:
            variants[customer_id] = variant

    skipped: Counter[str] = Counter()
    candidates: list[SeedCandidate] = []
    seen_record_ids: set[str] = set()
    seen_customers: set[str] = set()
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
        if record_id in seen_record_ids:
            # Duplicate record ids are refused (counted): one record
            # draws at most once, so the duplicate-draw check holds.
            skipped["transaction:duplicate-id"] += 1
            continue
        if customer_id in seen_customers:
            # First-wins: a second seed from the same customer is
            # skipped and counted. Last-wins would silently re-point
            # the draw, so it is forbidden here.
            skipped["transaction:duplicate-customer"] += 1
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
        tx_type = row.get("transaction_type")
        if not isinstance(tx_type, str) or not tx_type:
            skipped["transaction:missing-type"] += 1
            continue
        if tx_type.lower() not in {t.lower() for t in TRANSACTION_TYPES}:
            skipped["transaction:unexpected-type"] += 1
            continue
        if kind == "problem_transaction" and (
            tx_type.lower() not in {t.lower() for t in STUCK_TRANSACTION_TYPES}
        ):
            # Only Transfer/Payment problems ground stuck intents; every
            # other problem type is excluded here (counted, never drawn).
            skipped["transaction:non-stuck-type"] += 1
            continue
        channel = row.get("channel")
        if channel is not None and (
            not isinstance(channel, str) or channel.lower() not in {c.lower() for c in CHANNELS}
        ):
            skipped["transaction:unexpected-channel"] += 1
            continue
        fraud_flag = row.get("is_fraud")
        if not isinstance(fraud_flag, bool):
            # A missing fraud flag is an explicit skip reason: coercing
            # it to False would invent a clean negative control.
            skipped["transaction:missing-fraud-flag"] += 1
            continue
        seen_record_ids.add(record_id)
        seen_customers.add(customer_id)  # type: ignore[arg-type]
        candidates.append(
            SeedCandidate(
                record_id=record_id,
                customer_id=customer_id,  # type: ignore[arg-type]
                event_date=day,
                kind=kind,
                country_variant=variant,
                status=status,  # type: ignore[arg-type]
                transaction_type=tx_type,
                amount=float(row["amount"])
                if isinstance(row.get("amount"), (int, float))
                else None,
                currency=currency,  # type: ignore[arg-type]
                fraud_flag=fraud_flag,
                channel=channel if isinstance(channel, str) else None,
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
        if record_id in seen_record_ids:
            skipped["complaint:duplicate-id"] += 1
            continue
        if customer_id in seen_customers:
            # First-wins across tables too: one seed per customer.
            skipped["complaint:duplicate-customer"] += 1
            continue
        complaint_status = row.get("status")
        if not isinstance(complaint_status, str) or not complaint_status:
            skipped["complaint:missing-status"] += 1
            continue
        if complaint_status.lower() not in {s.lower() for s in COMPLAINT_STATUSES}:
            skipped["complaint:unexpected-status"] += 1
            continue
        breached = row.get("sla_breached")
        if breached is None:
            # A missing SLA flag is an explicit skip reason, not a silent
            # within-SLA default: the case-status grounding needs it.
            skipped["complaint:missing-sla"] += 1
            continue
        seen_record_ids.add(record_id)
        seen_customers.add(customer_id)  # type: ignore[arg-type]
        candidates.append(
            SeedCandidate(
                record_id=record_id,
                customer_id=customer_id,  # type: ignore[arg-type]
                event_date=day,
                kind="complaint",
                country_variant=variant,
                complaint_status=complaint_status,
                sla_state="breached" if bool(breached) else "within_sla",
            )
        )
    return candidates, dict(skipped)


def pull_seeds(
    candidates: list[SeedCandidate],
    *,
    quotas: dict[str, dict[str, int]] | None = None,
    floors: dict[str, int] | None = None,
    gate: dict[str, float],
    hard: dict[str, float],
    rng_seed: int = 20261005,
) -> tuple[dict[str, list[DrawnSeed]], SplitPullReport]:
    """Filter to usable records first, then sample to the P1 composition.

    Usability is the AND-condition (bucket and date agree) plus the P6
    amount margins for transaction rows with an amount. Excluded rows are
    attributed to their customer-bucket split, so the report states
    considered, usable, drawn and excluded counts per split. Every quota
    cell (split, kind, variant) draws exactly its quota or the pull
    raises ``SeedShortfall``: shortfalls are drawn short nowhere and
    backfilled never -- quotas are fail-closed, counted. Deterministic
    in ``rng_seed``: the same inputs always draw the same seeds.
    """
    wanted = quotas or {split: dict(kinds) for split, kinds in KIND_QUOTAS.items()}
    floors_wanted = floors or dict(COMPLAINT_FLOORS)
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
        floor = floors_wanted.get(split, 0)
        report.complaint_tight[split] = report.usable_complaints[split] < floor
        want = wanted.get(split, {})
        cells: dict[tuple[str, str], list[SeedCandidate]] = {
            (kind, variant): [] for kind in want for variant in VARIANTS
        }
        for candidate in pool:
            cell = cells.get((candidate.kind, candidate.country_variant))
            if cell is not None:
                cell.append(candidate)
        picked: list[SeedCandidate] = []
        for kind, kind_quota in want.items():
            targets = _variant_targets(kind_quota)
            for variant in VARIANTS:
                cell = sorted(cells[(kind, variant)], key=lambda c: c.record_id)
                need = targets[variant]
                if len(cell) < need:
                    raise SeedShortfall(
                        f"{split}/{kind}/{variant}: need {need}, have {len(cell)}: "
                        "quota shortfall fails closed, never backfilled"
                    )
                shuffled = cell[:]
                rng.shuffle(shuffled)
                picked.extend(shuffled[:need])
        drawn_complaints = sum(1 for c in picked if c.kind == "complaint")
        if drawn_complaints < floor:
            raise SeedShortfall(
                f"{split}: drew {drawn_complaints} complaint seeds below floor "
                f"{floor}: complaint heads are never backfilled"
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
        report.drawn_kinds[split] = dict(Counter(d.kind for d in drawn[split]))
        report.drawn_variants[split] = dict(
            Counter(d.candidate.country_variant for d in drawn[split])
        )
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
