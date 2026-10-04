"""Streaming, aggregate-only T-104 baseline calculations on contracted source rows.

Only the customer dimension, FX calendar, primary-key sets and numeric values needed
for exact linear percentiles remain in memory. No input row is written to disk.
"""

from __future__ import annotations

import bisect
import math
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date

from calvino.data.contracts import COUNTRIES, CURRENCIES
from calvino.data.inventory_access import InventoryError

SEGMENTS = frozenset({"Basic", "Plus", "Premium", "Student"})
CHANNELS = frozenset(
    {"Phone", "Chat", "Email", "WhatsApp", "App", "Web", "Web Chat", "Branch", "IVR"}
)
REASONS = frozenset({"Comercial", "Producto", "Queja", "Retención", "Transaccional", "Técnico"})
RESOLVED = frozenset({"Resolved", "Closed"})
OPEN = frozenset({"Open", "In Process", "Escalated"})
STATUSES = RESOLVED | OPEN | {"Rejected"}


def _date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        raise InventoryError("invalid baseline date") from None


def _number(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except ValueError:
        return math.nan
    return number if math.isfinite(number) else math.nan


def _boolean(value: str | None) -> bool | None:
    if value is None or value == "":
        return None
    if value.lower() in {"true", "1"}:
        return True
    if value.lower() in {"false", "0"}:
        return False
    raise InventoryError("invalid baseline boolean")


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lo = math.floor(position)
    hi = math.ceil(position)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo)


@dataclass
class Measure:
    """Tracks a statistic's valid, null and invalid cases separately."""

    valid: list[float] = field(default_factory=list)
    null: int = 0
    invalid: int = 0

    def add(self, value: str | None, *, nonnegative: bool = True) -> None:
        number = _number(value)
        if number is None:
            self.null += 1
        elif not math.isfinite(number) or (nonnegative and number < 0):
            self.invalid += 1
        else:
            self.valid.append(number)

    def rows(self, metric: str, population: int, excluded: int = 0) -> list[dict]:
        n = len(self.valid)
        return [
            _metric(
                f"{metric}_{suffix}",
                value,
                population,
                n,
                self.null,
                self.invalid,
                n,
                excluded,
            )
            for suffix, value in (
                ("mean", sum(self.valid) / n if n else None),
                ("median", _percentile(self.valid, 0.5)),
                ("p90", _percentile(self.valid, 0.9)),
            )
        ]


@dataclass
class Share:
    """Count booleans with a non-null denominator."""

    valid: int = 0
    true: int = 0
    null: int = 0

    def add(self, value: str | None) -> None:
        parsed = _boolean(value)
        if parsed is None:
            self.null += 1
        else:
            self.valid += 1
            self.true += parsed

    def row(self, metric: str, population: int) -> dict:
        return _metric(
            metric,
            self.true / self.valid if self.valid else None,
            population,
            self.valid,
            self.null,
            0,
            self.valid,
        )


def _metric(
    name: str,
    value: float | int | None,
    population: int,
    valid: int,
    null: int,
    invalid: int,
    denominator: int,
    excluded: int = 0,
) -> dict:
    return {
        "metric": name,
        "value": value,
        "n_population": population,
        "n_valid": valid,
        "n_null_excluded": null,
        "n_invalid_excluded": invalid,
        "n_unresolved_excluded": excluded,
        "denominator": denominator,
        "small_n": valid < 30,
    }


@dataclass
class CallSlice:
    """All call outcome accumulators for a single population and slice."""

    total: int = 0
    fcr: Share = field(default_factory=Share)
    escalation: Share = field(default_factory=Share)
    follow_up: Share = field(default_factory=Share)
    duration: Measure = field(default_factory=Measure)
    wait: Measure = field(default_factory=Measure)

    def add(self, row: dict[str, str | None]) -> None:
        self.total += 1
        self.fcr.add(row["was_resolved"])
        self.escalation.add(row["was_escalated"])
        self.follow_up.add(row["requires_followup"])
        self.duration.add(row["duration_seconds"])
        self.wait.add(row["wait_time_seconds"])

    def rows(self) -> list[dict]:
        return [
            self.fcr.row("fcr", self.total),
            self.escalation.row("escalation", self.total),
            self.follow_up.row("follow_up", self.total),
            *self.duration.rows("duration_seconds", self.total),
            *self.wait.rows("wait_time_seconds", self.total),
        ]


@dataclass
class ComplaintSlice:
    """Complaint outcomes, including separate native and converted claim amounts."""

    total: int = 0
    unresolved: int = 0
    resolved: int = 0
    still_open: int = 0
    sla: Share = field(default_factory=Share)
    resolution: Measure = field(default_factory=Measure)
    granted: int = 0
    granted_resolved: int = 0
    claims: dict[str, Measure] = field(default_factory=dict)
    usd: Measure = field(default_factory=Measure)
    fx_missing: int = 0
    currency_missing: int = 0

    def add(self, row: dict[str, str | None], usd: float | None) -> None:
        self.total += 1
        status = row["status"]
        if status not in STATUSES:
            raise InventoryError("unrecognized complaint status")
        is_resolved = status in RESOLVED
        self.resolved += is_resolved
        self.still_open += status in OPEN
        self.unresolved += not is_resolved
        if is_resolved:
            self.resolution.add(row["resolution_days"])
        self.sla.add(row["sla_breached"])
        granted = bool(row["compensation_granted"])
        self.granted += granted
        self.granted_resolved += granted and is_resolved
        amount = row["claimed_amount"]
        currency = row["currency"]
        if amount:
            parsed = _number(amount)
            if not currency:
                self.currency_missing += 1
            elif currency not in CURRENCIES:
                raise InventoryError("unrecognized claim currency")
            else:
                self.claims.setdefault(currency, Measure()).add(amount)
            if parsed is None or not math.isfinite(parsed) or parsed < 0:
                self.usd.add(amount)
            elif usd is None:
                self.fx_missing += 1 if currency else 0
                self.usd.add(None)
            else:
                self.usd.add(str(usd))
        else:
            self.usd.add(None)

    def rows(self) -> list[dict]:
        rows = [
            _metric("still_open_count", self.still_open, self.total, self.total, 0, 0, self.total),
            self.sla.row("sla_breached_share", self.total),
            _metric(
                "compensation_granted_share_of_all",
                self.granted / self.total if self.total else None,
                self.total,
                self.total,
                0,
                0,
                self.total,
            ),
            _metric(
                "compensation_granted_share_of_resolved",
                self.granted_resolved / self.resolved if self.resolved else None,
                self.total,
                self.resolved,
                0,
                0,
                self.resolved,
                self.unresolved,
            ),
            *self.resolution.rows("resolution_days", self.total, self.unresolved),
            *self.usd.rows("claimed_amount_usd", self.total),
            _metric(
                "claims_without_currency",
                self.currency_missing,
                self.total,
                self.total,
                0,
                0,
                self.total,
            ),
            _metric("claims_without_fx", self.fx_missing, self.total, self.total, 0, 0, self.total),
        ]
        for currency in CURRENCIES:
            measure = self.claims.get(currency, Measure())
            # All other currencies and absent claims are excluded from this
            # native-currency statistic, not silently removed from its population.
            measure.null = self.total - len(measure.valid) - measure.invalid
            rows.extend(measure.rows(f"claimed_amount_{currency}", self.total))
        return rows


class Baseline:
    """Consume the four tables in order and expose only aggregate rows."""

    def __init__(self) -> None:
        self.customers: dict[str, tuple[str, str]] = {}
        self.fx: dict[str, list[tuple[date, float]]] = {}
        self.calls: dict[tuple[str, str, str], CallSlice] = {}
        self.complaints: dict[tuple[str, str, str], ComplaintSlice] = {}
        self.rows: Counter[str] = Counter()
        self.unknown: Counter[str] = Counter()
        self.non_target: Counter[str] = Counter()
        self.known_defects: Counter[str] = Counter()
        self.date_range: dict[str, tuple[date, date]] = {}
        self._seen: dict[str, set[object]] = {}

    def _date_range(self, table: str, value: str | None) -> None:
        parsed = _date(value)
        if parsed is not None:
            first, last = self.date_range.get(table, (parsed, parsed))
            self.date_range[table] = min(first, parsed), max(last, parsed)

    def _unique(self, table: str, key: object) -> None:
        if key is None or key == "" or key in self._seen.setdefault(table, set()):
            raise InventoryError(f"missing or duplicate primary key in {table}")
        self._seen[table].add(key)
        self.rows[table] += 1

    def load_customers(self, records: Iterable[dict[str, str | None]]) -> None:
        for row in records:
            key = row["customer_id"]
            self._unique("customers", key)
            country, segment = row["country"], row["segment"]
            if country not in COUNTRIES:
                raise InventoryError("unrecognized customer country")
            if segment not in SEGMENTS:
                self.unknown["customer_segment"] += 1
            self.customers[key] = (country, segment if segment in SEGMENTS else "(other)")

    def load_fx(self, records: Iterable[dict[str, str | None]]) -> None:
        for row in records:
            day = _date(row["date"])
            src, target = row["source_currency"], row["target_currency"]
            self._unique("daily_exchange_rates", (day, src, target))
            rate = _number(row["exchange_rate"])
            if day is None or rate is None or not math.isfinite(rate) or rate <= 0:
                raise InventoryError("invalid exchange rate")
            self._date_range("daily_exchange_rates", row["date"])
            if src not in CURRENCIES or target not in CURRENCIES:
                raise InventoryError("unrecognized exchange-rate currency")
            if target == "USD":
                self.fx.setdefault(src, []).append((day, rate))
        for rates in self.fx.values():
            rates.sort()

    def _customer(self, row: dict[str, str | None]) -> tuple[str, str]:
        try:
            return self.customers[row["customer_id"]]
        except KeyError:
            raise InventoryError("unmatched baseline customer") from None

    def load_calls(self, records: Iterable[dict[str, str | None]]) -> None:
        for row in records:
            self._unique("call_center_interactions", row["interaction_id"])
            country, segment = self._customer(row)
            self._date_range("call_center_interactions", row.get("interaction_date"))
            channel = row["channel"]
            if channel not in CHANNELS:
                self.unknown["call_channel"] += 1
                channel = "(other)"
            reason = row["reason_category"]
            if reason is None:
                raise InventoryError("missing call reason category")
            if reason not in REASONS:
                self.unknown["call_reason_category"] += 1
            if row.get("contact_reason") and row["contact_reason"] == reason:
                self.known_defects["CI-REASON-REPEATS"] += 1
            slices = (
                ("overall", "all"),
                ("country", country),
                ("segment", segment),
                ("channel", channel),
                ("country_x_segment", f"{country} / {segment}"),
            )
            for population in (
                ("all interactions", "Transaccional")
                if reason == "Transaccional"
                else ("all interactions",)
            ):
                for kind, value in slices:
                    self.calls.setdefault((population, kind, value), CallSlice()).add(row)

    def _usd(self, row: dict[str, str | None]) -> float | None:
        amount = _number(row["claimed_amount"])
        currency = row["currency"]
        if amount is None or not math.isfinite(amount) or amount < 0:
            return None
        if currency == "USD":
            return amount
        if currency not in CURRENCIES:
            return None
        day = _date(row["creation_date"])
        if day is None:
            return None
        rates = self.fx.get(currency, [])
        at = bisect.bisect_right(rates, (day, math.inf)) - 1
        return amount * rates[at][1] if at >= 0 else None

    def load_complaints(self, records: Iterable[dict[str, str | None]]) -> None:
        for row in records:
            self._unique("complaints", row["complaint_id"])
            country, _ = self._customer(row)
            self._date_range("complaints", row["creation_date"])
            if not row.get("origin_interaction_id"):
                self.known_defects["CP-ORIGIN-NULL"] += 1
            if row["claimed_amount"] and not row["currency"]:
                self.known_defects["CP-AMOUNT-NO-CURRENCY"] += 1
            case = row["case_type"] or "(null)"
            # Case types are bounded before they enter an aggregate output.
            if case not in {"Request", "Suggestion", "Complaint", "Claim", "(null)"}:
                self.unknown["case_type"] += 1
                case = "(other)"
            category = row["category"]
            if category is None:
                self.unknown["complaint_category_null"] += 1
            elif category != "Transactions":
                # Non-target categories are valid for "all complaints"; do not
                # mislabel them as unknown without an authoritative taxonomy.
                self.non_target["complaint_category"] += 1
            usd = self._usd(row)
            for population in (
                ("all complaints", "Transactions")
                if category == "Transactions"
                else ("all complaints",)
            ):
                for kind, value in (
                    ("overall", "all"),
                    ("country", country),
                    ("case_type", case),
                    ("country_x_case_type", f"{country} / {case}"),
                ):
                    self.complaints.setdefault((population, kind, value), ComplaintSlice()).add(
                        row, usd
                    )

    def output(self, table: str) -> list[dict]:
        source = self.calls if table == "interactions" else self.complaints
        return [
            {
                "population": population,
                "slice_type": kind,
                "slice_value": value,
                **metric,
            }
            for (population, kind, value), item in sorted(source.items())
            for metric in item.rows()
        ]
