"""Immutable fixture records, hashing and JSONL input parsing for T-105."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from calvino.evaluation.oracle import ORACLE_VERSION, ExpectedOutcome

PRODUCER_COMMIT = "fixture-commit-v1"
SOURCE_CONTRACT_VERSION = "freshness-source-v1"
SPLIT_CONTRACT_VERSION = "TSD-015"
REPROCESSING_WINDOW_DAYS = 30
ALLOWED_COUNTRIES = frozenset({"MX", "CO", "AR"})
ALLOWED_CURRENCIES = frozenset({"MXN", "COP", "ARS", "USD"})
SUPPORTED_KINDS = frozenset({"transaction", "interaction", "complaint"})


class FreshnessInputError(ValueError):
    """A fixture row cannot be interpreted safely."""


class StaleArtifactError(ValueError):
    """An artifact does not match the explicitly selected input snapshot."""


class RevisionDisposition(StrEnum):
    """Primary outcome for one observed synthetic source revision."""

    ACCEPTED = "accepted"
    QUARANTINED_LATE = "quarantined_late"
    QUARANTINED_INVALID_CORRECTION = "quarantined_invalid_correction"
    SUPERSEDED = "superseded"
    FROZEN_DRIFT = "frozen_drift"


@dataclass(frozen=True, slots=True)
class RevisionStatus:
    """One primary disposition plus all applicable, sorted reason codes."""

    record_id: str
    source_file_id: str
    source_file_sha256: str
    revision_no: int
    disposition: RevisionDisposition
    reasons: tuple[str, ...] = ()
    lineage_artifact_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "reasons", tuple(sorted(set(self.reasons))))


@dataclass(frozen=True, slots=True)
class SourceRevision:
    """One synthetic source row revision and its source-file provenance."""

    record_id: str
    revision_no: int
    source_file_id: str
    process_date: date
    arrival_date: date
    customer_id: str
    country_variant: str
    event_date: date
    record_kind: str
    payload: Mapping[str, Any]
    frozen_suite_sentinel: bool = False
    validation_errors: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> SourceRevision:
        required = (
            "record_id",
            "revision_no",
            "source_file_id",
            "process_date",
            "arrival_date",
            "customer_id",
            "country_variant",
            "event_date",
            "record_kind",
            "payload",
        )
        missing = [key for key in required if key not in raw]
        if missing:
            raise FreshnessInputError(
                f"source row is missing identity fields: {', '.join(missing)}"
            )

        revision_value = raw["revision_no"]
        if type(revision_value) is not int:
            raise FreshnessInputError("revision_no must be a positive integer")
        revision_no = revision_value
        if revision_no < 1:
            raise FreshnessInputError("revision_no must be a positive integer")

        def parse_identity(name: str) -> str:
            value = raw[name]
            if not isinstance(value, str) or not value.strip():
                raise FreshnessInputError(f"{name} must be a non-empty string")
            return value

        def parse_day(name: str) -> date:
            value = raw[name]
            if not isinstance(value, str):
                raise FreshnessInputError(f"{name} must be an ISO date")
            try:
                return date.fromisoformat(value)
            except ValueError as exc:
                raise FreshnessInputError(f"{name} must be an ISO date") from exc

        payload = raw["payload"]
        if not isinstance(payload, Mapping):
            raise FreshnessInputError("payload must be a JSON object")
        raw_sentinel = raw.get("frozen_suite_sentinel", False)
        revision = cls(
            record_id=parse_identity("record_id"),
            revision_no=revision_no,
            source_file_id=parse_identity("source_file_id"),
            process_date=parse_day("process_date"),
            arrival_date=parse_day("arrival_date"),
            customer_id=parse_identity("customer_id"),
            country_variant=parse_identity("country_variant"),
            event_date=parse_day("event_date"),
            record_kind=parse_identity("record_kind"),
            payload=dict(payload),
            frozen_suite_sentinel=raw_sentinel is True,
            validation_errors=(),
        )
        errors = list(revision.contract_errors())
        if type(raw_sentinel) is not bool:
            errors.append("invalid_frozen_sentinel")
        return replace(revision, validation_errors=tuple(sorted(set(errors))))

    def contract_errors(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.record_id or not self.customer_id or not self.source_file_id:
            errors.append("empty_identity")
        if self.arrival_date < self.process_date:
            errors.append("arrival_before_process_date")
        if self.country_variant not in ALLOWED_COUNTRIES:
            errors.append("unsupported_country")
        if self.record_kind not in SUPPORTED_KINDS:
            errors.append("unsupported_record_kind")
        if not isinstance(self.frozen_suite_sentinel, bool):
            errors.append("invalid_frozen_sentinel")

        if self.record_kind == "transaction":
            required = {
                "amount",
                "currency",
                "status",
                "intent",
                "ambiguous",
                "owner",
                "fraud_flag",
                "in_scope",
            }
            if required - self.payload.keys():
                errors.append("incomplete_transaction_payload")
            currency = self.payload.get("currency")
            if currency not in ALLOWED_CURRENCIES:
                errors.append("unsupported_currency")
            try:
                amount = Decimal(str(self.payload.get("amount")))
            except (InvalidOperation, TypeError):
                errors.append("invalid_amount")
            else:
                if not amount.is_finite() or amount < 0:
                    errors.append("invalid_amount")
            if self.payload.get("status") not in {"Approved", "Declined", "Pending", "Reversed"}:
                errors.append("invalid_transaction_status")
            if self.payload.get("intent") not in {
                "retry",
                "cancel",
                "explain",
                "open_case",
                "case_status",
                "human",
                "manipulation",
                "none",
            }:
                errors.append("invalid_intent")
            for name in ("ambiguous", "owner", "fraud_flag", "in_scope"):
                if type(self.payload.get(name)) is not bool:
                    errors.append(f"invalid_{name}")
        elif self.record_kind == "interaction":
            required = {"was_resolved", "was_escalated", "requires_followup"}
            if required - self.payload.keys():
                errors.append("incomplete_interaction_payload")
            for name in required:
                if self.payload.get(name) is not None and type(self.payload[name]) is not bool:
                    errors.append(f"invalid_{name}")
        elif self.record_kind == "complaint":
            required = {"sla_breached", "status"}
            if required - self.payload.keys():
                errors.append("incomplete_complaint_payload")
            if (
                self.payload.get("sla_breached") is not None
                and type(self.payload["sla_breached"]) is not bool
            ):
                errors.append("invalid_sla_breached")

        return tuple(sorted(set(errors)))

    @property
    def content_sha256(self) -> str:
        """Hash logical row content, excluding arrival and transport metadata."""
        content = {
            "record_id": self.record_id,
            "process_date": self.process_date.isoformat(),
            "customer_id": self.customer_id,
            "country_variant": self.country_variant,
            "event_date": self.event_date.isoformat(),
            "record_kind": self.record_kind,
            "payload": dict(self.payload),
            "frozen_suite_sentinel": self.frozen_suite_sentinel,
        }
        return sha256_json(content)

    @property
    def source_file_sha256(self) -> str:
        """Hash the observed transport row for audit, not the materialized partition."""
        observed = {
            "source_file_id": self.source_file_id,
            "arrival_date": self.arrival_date.isoformat(),
            "content_sha256": self.content_sha256,
        }
        return sha256_json(observed)

    @property
    def lineage_artifact_id(self) -> str:
        return f"revision:{self.record_id}:r{self.revision_no}:{self.source_file_sha256[:12]}"

    def partition_row(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "content_sha256": self.content_sha256,
            "process_date": self.process_date.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class ArtifactLineage:
    """Immutable lineage for one source or derived artifact."""

    artifact_id: str
    artifact_kind: str
    parent_artifact_ids: tuple[str, ...]
    source_hashes: tuple[tuple[str, str], ...]
    contract_versions: tuple[tuple[str, str], ...]
    producer_commit: str = PRODUCER_COMMIT

    def __post_init__(self) -> None:
        if not self.artifact_id or not self.artifact_kind or not self.producer_commit:
            raise FreshnessInputError("artifact lineage identity fields must be non-empty")
        parents = tuple(sorted(set(self.parent_artifact_ids)))
        source_hashes = tuple(sorted(self.source_hashes))
        contract_versions = tuple(sorted(self.contract_versions))
        if len({key for key, _ in source_hashes}) != len(source_hashes):
            raise FreshnessInputError("artifact lineage contains duplicate source hash ids")
        if len({key for key, _ in contract_versions}) != len(contract_versions):
            raise FreshnessInputError("artifact lineage contains duplicate contract ids")
        for source_id, digest in source_hashes:
            if (
                not source_id
                or len(digest) != 64
                or any(c not in "0123456789abcdef" for c in digest)
            ):
                raise FreshnessInputError("source hashes must be lowercase SHA-256 digests")
        object.__setattr__(self, "parent_artifact_ids", parents)
        object.__setattr__(self, "source_hashes", source_hashes)
        object.__setattr__(self, "contract_versions", contract_versions)


@dataclass(frozen=True, slots=True)
class FixtureSeedFactRow:
    """Seed-fact stand-in for a policy-banded source amount."""

    seed_id: str
    source_record_id: str
    split: str
    amount: str
    currency: str
    amount_band: str
    policy_version: str
    expected_outcome: ExpectedOutcome
    lineage_id: str


@dataclass(frozen=True, slots=True)
class FixtureProxyLabelRow:
    """Proxy-label stand-in derived from an interaction or complaint row."""

    label_id: str
    source_record_id: str
    proxy_label: str
    value: bool
    split: str
    lineage_id: str


@dataclass(frozen=True, slots=True)
class FixtureBaselineCell:
    """Small aggregate stand-in for a measured human-baseline slice."""

    cell_id: str
    proxy_label: str
    split: str
    numerator: int
    denominator: int
    lineage_id: str


@dataclass(frozen=True, slots=True)
class CandidateEvidenceRow:
    """Fixture-only evidence record linked to source-derived stand-ins."""

    evidence_id: str
    source_record_ids: tuple[str, ...]
    source_artifact_ids: tuple[str, ...]
    evidence_digest: str
    lineage_id: str


@dataclass(frozen=True, slots=True)
class FreshnessReport:
    """Deterministic changes, dispositions and currentness for one update."""

    revision_statuses: tuple[RevisionStatus, ...]
    pending_correction_ids: tuple[str, ...]
    rebuilt_artifact_ids: tuple[str, ...]
    invalidated_artifact_ids: tuple[str, ...]
    changed_seed_fact_ids: tuple[str, ...]
    unchanged_seed_fact_ids: tuple[str, ...]
    changed_proxy_label_ids: tuple[str, ...]
    unchanged_proxy_label_ids: tuple[str, ...]
    changed_baseline_cell_ids: tuple[str, ...]
    unchanged_baseline_cell_ids: tuple[str, ...]
    changed_evidence_ids: tuple[str, ...]
    unchanged_evidence_ids: tuple[str, ...]
    blocked_frozen_artifact_ids: tuple[str, ...]
    frozen_set_drift_ids: tuple[str, ...]
    is_current_to_latest_observed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "revision_statuses": [
                {
                    "record_id": item.record_id,
                    "revision_no": item.revision_no,
                    "source_file_id": item.source_file_id,
                    "source_file_sha256": item.source_file_sha256,
                    "disposition": item.disposition.value,
                    "reasons": list(item.reasons),
                    "lineage_artifact_id": item.lineage_artifact_id,
                }
                for item in self.revision_statuses
            ],
            "pending_correction_ids": list(self.pending_correction_ids),
            "rebuilt_artifact_ids": list(self.rebuilt_artifact_ids),
            "invalidated_artifact_ids": list(self.invalidated_artifact_ids),
            "changed_seed_fact_ids": list(self.changed_seed_fact_ids),
            "unchanged_seed_fact_ids": list(self.unchanged_seed_fact_ids),
            "changed_proxy_label_ids": list(self.changed_proxy_label_ids),
            "unchanged_proxy_label_ids": list(self.unchanged_proxy_label_ids),
            "changed_baseline_cell_ids": list(self.changed_baseline_cell_ids),
            "unchanged_baseline_cell_ids": list(self.unchanged_baseline_cell_ids),
            "changed_evidence_ids": list(self.changed_evidence_ids),
            "unchanged_evidence_ids": list(self.unchanged_evidence_ids),
            "blocked_frozen_artifact_ids": list(self.blocked_frozen_artifact_ids),
            "frozen_set_drift_ids": list(self.frozen_set_drift_ids),
            "is_current_to_latest_observed": self.is_current_to_latest_observed,
        }


@dataclass(frozen=True, slots=True)
class UpdatePlan:
    """Immutable accepted snapshots and rebuild/invalidation decisions."""

    accepted_revisions: Mapping[str, SourceRevision]
    frozen_revisions: Mapping[str, SourceRevision]
    frozen_members: tuple[str, ...]
    revision_statuses: tuple[RevisionStatus, ...]
    revision_lineage_by_id: Mapping[str, ArtifactLineage]
    quarantined_initial_revisions: tuple[SourceRevision, ...]
    pending_correction_ids: tuple[str, ...]
    frozen_set_drift_ids: tuple[str, ...]
    blocked_frozen_artifact_ids: tuple[str, ...]
    invalidated_artifact_ids: tuple[str, ...]
    expected_source_hashes: Mapping[str, str]
    current_contract_versions: Mapping[str, str]
    gate_limits: Mapping[str, Decimal]
    gate_table_digest: str


@dataclass(frozen=True, slots=True)
class FreshnessState:
    """Accepted initial snapshot plus its quarantined and frozen lineage."""

    accepted_revisions: Mapping[str, SourceRevision]
    quarantined_initial_revisions: tuple[SourceRevision, ...]
    frozen_members: tuple[str, ...]
    lineage_by_id: Mapping[str, ArtifactLineage]
    revision_lineage_by_id: Mapping[str, ArtifactLineage]
    artifact_values: Mapping[str, Any]
    source_hashes: Mapping[str, str]
    contract_versions: Mapping[str, str]
    gate_limits: Mapping[str, Decimal]
    gate_table_digest: str
    initial_statuses: tuple[RevisionStatus, ...]


@dataclass(frozen=True, slots=True)
class _ArtifactBundle:
    """Derived rows and lineage for one pair of mutable/frozen snapshots."""

    lineages: Mapping[str, ArtifactLineage]
    values: Mapping[str, Any]
    source_hashes: Mapping[str, str]
    seeds: Mapping[str, FixtureSeedFactRow]
    proxy_labels: Mapping[str, FixtureProxyLabelRow]
    baseline_cells: Mapping[str, FixtureBaselineCell]
    evidence: Mapping[str, CandidateEvidenceRow]


def _lineage(
    artifact_id: str,
    artifact_kind: str,
    *,
    parents: Sequence[str] = (),
    source_hashes: Mapping[str, str] | None = None,
    contract_versions: Mapping[str, str],
) -> ArtifactLineage:
    """Create one canonical immutable artifact lineage record."""
    return ArtifactLineage(
        artifact_id=artifact_id,
        artifact_kind=artifact_kind,
        parent_artifact_ids=tuple(parents),
        source_hashes=tuple((source_hashes or {}).items()),
        contract_versions=tuple(contract_versions.items()),
    )


def _current_contract_versions(gate_digest: str) -> dict[str, str]:
    """Return all versions participating in T-105 freshness decisions."""
    return {
        "source": SOURCE_CONTRACT_VERSION,
        "split": SPLIT_CONTRACT_VERSION,
        "oracle": ORACLE_VERSION,
        "policy": "v2",
        "policy_gate_table": gate_digest,
    }


def _is_late(revision: SourceRevision) -> bool:
    """Whether a first-seen partition arrived beyond the inclusive window."""
    return (revision.arrival_date - revision.process_date).days > REPROCESSING_WINDOW_DAYS


def _revision_status(
    revision: SourceRevision,
    disposition: RevisionDisposition,
    *reasons: str,
) -> RevisionStatus:
    return RevisionStatus(
        revision.record_id,
        revision.source_file_id,
        revision.source_file_sha256,
        revision.revision_no,
        disposition,
        tuple(reasons),
        revision.lineage_artifact_id,
    )


def _revision_lineage(
    revision: SourceRevision, previous_revision: SourceRevision | None = None
) -> ArtifactLineage:
    parent_ids = (previous_revision.lineage_artifact_id,) if previous_revision else ()
    return _lineage(
        revision.lineage_artifact_id,
        "source_revision",
        parents=parent_ids,
        source_hashes={f"row:{revision.record_id}": revision.content_sha256},
        contract_versions={"source": SOURCE_CONTRACT_VERSION},
    )


def canonical_json(value: Any) -> str:
    """Stable JSON used for fixture hashes and reports."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def default_policy_path() -> Path:
    """Return the repository's immutable v2 policy file."""
    return Path(__file__).resolve().parents[3] / "policy" / "v2.yaml"


def load_gate_limits(policy_path: Path | None = None) -> tuple[dict[str, Decimal], str]:
    """Load v2's gate table and hash only its canonical sorted mapping."""
    path = policy_path or default_policy_path()
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        mapping = raw["gate"]["allow_amount_limit"]
        limits = {str(key): Decimal(str(value)) for key, value in mapping.items()}
    except (OSError, KeyError, TypeError, yaml.YAMLError, InvalidOperation) as exc:
        raise FreshnessInputError("could not load policy gate amount limits") from exc
    if set(limits) != ALLOWED_CURRENCIES or any(not value.is_finite() for value in limits.values()):
        raise FreshnessInputError("policy gate table must cover the four fixture currencies")
    canonical_limits = {
        key: int(value) if value == value.to_integral_value() else str(value)
        for key, value in sorted(limits.items())
    }
    digest = sha256_json(canonical_limits)
    return limits, digest


def read_source_revisions(path: Path) -> tuple[SourceRevision, ...]:
    """Read JSONL fixture rows without consulting the clock or external data."""
    revisions: list[SourceRevision] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise FreshnessInputError(f"{path.name}:{line_number}: invalid JSON") from exc
        if not isinstance(raw, Mapping):
            raise FreshnessInputError(f"{path.name}:{line_number}: row must be a JSON object")
        revisions.append(SourceRevision.from_mapping(raw))
    return tuple(revisions)


def _accepted_source_errors(revision: SourceRevision) -> tuple[str, ...]:
    return revision.validation_errors
