"""Team-generated customer message set (TSD-019, T-106).

Seed registries, the brief-to-labels derivation table, the record-facts to
``OracleFacts`` bridge (reusing the TSD-013 oracle, never a competing one),
text normalisation with Jaccard near-duplicate checks, and the offline
registry check runner (L1-L5 by reference to ``calvino.data.leakage``).

Every test and check here runs offline on synthetic fixtures: no network,
no GPU, no keys, no dataset, no salt. Portuguese rows are rejected by
design (T-203 owns Portuguese); BRL is rejected with them.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

from calvino.data.leakage import (
    CandidateInput,
    SeedEntry,
    Violation,
    check_l1_customer_isolation,
    check_l2_time_order,
    check_l3_dataset_text,
    check_l4_generation_isolation,
    check_l5_gold_held_out,
)
from calvino.evaluation.oracle import OracleFacts, oracle_outcome

SET_VERSION = "v1"
RUBRIC_VERSION = "v1"
SALT_VERSION = "salt-v1"

Split = Literal["train", "calibration", "test"]
SPLITS: tuple[str, str, str] = ("train", "calibration", "test")

SeedKind = Literal[
    "problem_transaction",
    "clean_transaction",
    "other_customer",
    "complaint",
    "no_record",
    "rewording",
    "hand_written",
]

CountryVariant = Literal["MX", "CO", "AR"]
LANGUAGE_VARIANTS = ("es-MX", "es-CO", "es-AR")
COUNTRY_CURRENCY: dict[str, str] = {"MX": "MXN", "CO": "COP", "AR": "ARS"}
ALLOWED_CURRENCIES = ("MXN", "COP", "ARS", "USD")

ReviewVerdict = Literal["unreviewed", "pass", "corrected", "fail"]

# A generation brief intent is either a TSD-013 oracle intent or one of the
# three non-stuck heads P1 names (dispute / fraud-report / out-of-scope),
# which the derivation table maps onto oracle intents below.
BriefIntent = Literal[
    "explain",
    "cancel",
    "retry",
    "open_case",
    "case_status",
    "human",
    "manipulation",
    "none",
    "dispute",
    "fraud_report",
    "out_of_scope",
]

AdversarialKind = Literal["wrong_data", "missing_data", "injection", "multilingual", "edge"]

# Brief intents that ground stuck-payment rows (the six stuck intents of
# labels.StuckIntent, in oracle-intent vocabulary).
STUCK_BRIEF_INTENTS = ("explain", "cancel", "retry", "open_case", "case_status", "human")


@dataclass(frozen=True)
class BriefDefaults:
    """The deterministic defaults one brief intent carries (TSD-019 table)."""

    workflow_area: str | None
    stuck_intent: str | None
    oracle_intent: str
    in_scope: bool


BRIEF_DEFAULTS: dict[str, BriefDefaults] = {
    "explain": BriefDefaults("stuck payment", "status", "explain", True),
    "cancel": BriefDefaults("stuck payment", "cancel", "cancel", True),
    "retry": BriefDefaults("stuck payment", "retry", "retry", True),
    "open_case": BriefDefaults("stuck payment", "open a case", "open_case", True),
    "case_status": BriefDefaults("stuck payment", "case status", "case_status", True),
    "human": BriefDefaults("stuck payment", "talk to a person", "human", True),
    # Non-stuck heads: a dispute or fraud report reads as an explanation
    # request to the oracle; the fraud flag (fraud-report) and the
    # needs-person label carry the escalation, not the intent.
    "dispute": BriefDefaults("dispute or unrecognised charge", None, "explain", True),
    "fraud_report": BriefDefaults("fraud or stolen access", None, "explain", True),
    "out_of_scope": BriefDefaults("out of scope", None, "none", False),
    # An injection carrier keeps its carrier workflow at review; the
    # default pins nothing so an unreviewed injection row cannot pose as
    # a settled stuck intent. The oracle still sees "manipulation".
    "manipulation": BriefDefaults("stuck payment", None, "manipulation", True),
    # An unrecognisable empty/garbled message is in-workflow but ambiguous:
    # the oracle clarifies it. Explicit out-of-scope requests use the
    # separate out_of_scope brief above.
    "none": BriefDefaults(None, None, "none", True),
}

CLEAR_AMBIGUOUS_KINDS = ("wrong_data", "missing_data", "multilingual")
NEEDS_PERSON_INTENTS = ("human", "dispute", "fraud_report")


def derive_seed_key(
    *,
    salt: str,
    set_version: str,
    split: str,
    kind: str,
    record_id: str,
    role: str = "base",
) -> str:
    """The opaque deterministic seed key (TSD-019 seed-keys section).

    ``{version}-{12 hex of sha256(salt | version | split | kind |
    record_id | role)}``. No random nonce: the same inputs always give the
    same key, so regeneration is checkable given the salt and the
    pointer log. Never a record pointer: the hash reveals no record,
    customer or date.
    """
    raw = "|".join((salt, set_version, split, kind, record_id, role))
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"{set_version}-{digest}"


def salted_customer_hash(customer_id: str, salt: str) -> str:
    """The committed customer identity: truncated salted hash, facts only.

    ``sha256(customer_id + salt)[:16]`` (hex): enough for the L1 equality
    check, not enough to identify anyone. The salt value is never
    committed (TSD-019 P3).
    """
    return hashlib.sha256((customer_id + salt).encode("utf-8")).hexdigest()[:16]


_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")


def _strip_emoji(text: str) -> str:
    return "".join(char for char in text if unicodedata.category(char) != "So")


def normalize_text(text: str) -> str:
    """The shared normalisation every overlap check uses.

    Unicode NFKC, lowercase, emoji and punctuation stripped, whitespace
    collapsed to single spaces and trimmed.
    """
    lowered = unicodedata.normalize("NFKC", text).lower()
    no_emoji = _strip_emoji(lowered)
    no_punct = _PUNCT_RE.sub(" ", no_emoji)
    return _WS_RE.sub(" ", no_punct).strip()


def jaccard(first: str, second: str) -> float:
    """Jaccard similarity over normalized whitespace-split token sets.

    ``|A cap B| / |A cup B|``. Empty token sets score 0.0 here; callers
    apply the empty-result exemption (raw-text comparison) instead.
    """
    left = set(first.split())
    right = set(second.split())
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


NEAR_DUPLICATE_THRESHOLD = 0.90


def is_near_duplicate(
    first: str, second: str, *, threshold: float = NEAR_DUPLICATE_THRESHOLD
) -> bool:
    """Whether two messages collide: exact post-normalisation match or
    Jaccard at or above threshold. When either side normalizes empty
    (empty or emoji-only rows), the Jaccard check is skipped and raw
    texts must differ instead.
    """
    norm_first = normalize_text(first)
    norm_second = normalize_text(second)
    if not norm_first or not norm_second:
        return first == second
    if norm_first == norm_second:
        return True
    return jaccard(norm_first, norm_second) >= threshold


class RecordFacts(BaseModel):
    """The committed seed facts for one registry row: facts only.

    No raw ids, no raw amounts (bands only), no texts: the band carries
    the oracle signal and the amount never leaves the pull.
    """

    model_config = {"extra": "forbid"}

    kind: SeedKind
    status: str | None = None
    transaction_type: str | None = None
    amount_band: Literal["under_gate", "over_gate"] | None = None
    currency: Literal["MXN", "COP", "ARS", "USD"] | None = None
    fraud_flag: bool = False
    channel: str | None = None
    complaint_status: str | None = None
    sla_state: str | None = None


class SeedRow(BaseModel):
    """One committed registry row (``seeds.{split}.jsonl``)."""

    model_config = {"extra": "forbid"}

    seed_key: str = Field(min_length=1)
    split: Split
    prompt_id: str = Field(min_length=1)
    kind: SeedKind
    parent_seed_key: str | None = None
    customer_hash: str = Field(min_length=1)
    country_variant: CountryVariant
    record_facts: RecordFacts
    event_date: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    gate_table_hash: str | None = None


class MessageLabels(BaseModel):
    """The reviewed (or defaulted) classifier labels on one message."""

    model_config = {"extra": "forbid"}

    workflow_area: str | None = Field(default=None, min_length=1)
    stuck_intent: str | None = None
    clear_enough: bool = True
    needs_person: bool = False
    injection: bool = False

    @model_validator(mode="after")
    def an_unset_area_must_be_unclear(self) -> MessageLabels:
        """An omitted workflow area cannot be a target on a clear message."""
        if self.workflow_area is None and self.clear_enough:
            raise ValueError("workflow_area may be unset only when clear_enough is false")
        return self

    def validate_area_for_intent(self, oracle_intent: str) -> None:
        """Only the unclassifiable `none` intent permits an unset area."""
        if self.workflow_area is None and oracle_intent != "none":
            raise ValueError("workflow_area may be unset only for oracle intent 'none'")


class MessageOracleFacts(BaseModel):
    """The oracle inputs derived for one message (reviewed or defaulted)."""

    model_config = {"extra": "forbid"}

    intent: str = Field(min_length=1)
    ambiguous: bool = False
    status: str | None = None
    owner: bool = True
    amount_band: Literal["under_gate", "over_gate"] = "under_gate"
    fraud_flag: bool = False
    in_scope: bool = True


class MessageProvenance(BaseModel):
    """Where one message came from: prompt version and model or hand."""

    model_config = {"extra": "forbid"}

    prompt_id: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    generated_at: str = ""
    reviewer: str = ""
    review_verdict: ReviewVerdict = "unreviewed"


class MessageRow(BaseModel):
    """One committed message row (``{train,calibration,test}.jsonl``)."""

    model_config = {"extra": "forbid"}

    msg_id: str = Field(min_length=1)
    split: Split
    language_variant: Literal["es-MX", "es-CO", "es-AR"]
    message: str = Field(min_length=1)
    seed_key: str = Field(min_length=1)
    labels: MessageLabels
    oracle_facts: MessageOracleFacts
    provenance: MessageProvenance
    synthetic: bool = True

    @model_validator(mode="after")
    def workflow_area_matches_oracle_intent(self) -> MessageRow:
        """Require an unlabelled area to correspond to an unclear `none` row."""
        self.labels.validate_area_for_intent(self.oracle_facts.intent)
        return self


def derive_defaults(
    *,
    brief_intent: str,
    adversarial_kind: str | None,
    seed_kind: str,
) -> tuple[MessageLabels, MessageOracleFacts]:
    """Brief-derived defaults: the oracle is defined on unreviewed rows.

    Every review-sourced field has a deterministic default from the brief
    and the seed row; rows outside the review sample keep these, and
    review may only move a field to a logged correction.
    """
    brief = BRIEF_DEFAULTS[brief_intent]
    probing = adversarial_kind in CLEAR_AMBIGUOUS_KINDS
    ambiguous = brief_intent == "none" or probing
    injecting = brief_intent == "manipulation" or adversarial_kind == "injection"

    clear_enough = not ambiguous
    needs_person = brief_intent in NEEDS_PERSON_INTENTS

    labels = MessageLabels(
        workflow_area=brief.workflow_area,
        stuck_intent=brief.stuck_intent,
        clear_enough=clear_enough,
        needs_person=needs_person,
        injection=injecting,
    )
    facts = MessageOracleFacts(
        intent=brief.oracle_intent,
        ambiguous=ambiguous,
        status=None,
        owner=True,
        amount_band="under_gate",
        fraud_flag=False,
        in_scope=brief.in_scope,
    )
    return labels, facts


def load_gate_limits(policy_path: str | Path) -> tuple[str, dict[str, float], dict[str, float]]:
    """The gate and hard-rule amount tables of one released policy file."""
    data = yaml.safe_load(Path(policy_path).read_text(encoding="utf-8"))
    version = str(data["version"])
    gate = {str(code): float(value) for code, value in data["gate"]["allow_amount_limit"].items()}
    hard = {str(code): float(value) for code, value in data["hard_rules"]["amount_limit"].items()}
    return version, gate, hard


def amount_band_for(amount: float, currency: str, gate_limits: dict[str, float]) -> str:
    """The seed amount band (TSD-019 P6) against one policy's gate table."""
    if amount <= gate_limits[currency]:
        return "under_gate"
    return "over_gate"


def gate_table_hash(gate_limits: dict[str, float]) -> str:
    """The canonical hash of one policy's gate table (TSD-019 P6 evidence).

    Stored per banded seed instead of the raw limit it replaced: equal
    tables hash equal, so the oracle-path guard detects any table drift
    without committing a single limit value.
    """
    import json  # noqa: PLC0415

    canonical = json.dumps(
        {code: float(gate_limits[code]) for code in sorted(gate_limits)},
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def usable_amount(
    amount: float, currency: str, gate: dict[str, float], hard: dict[str, float]
) -> bool:
    """Whether a seed amount sits clear of both policy lines (TSD-019 P6).

    Excluded: within ±20% of any gate limit, within 20% below the
    hard-rule limit, or anywhere above it — so small limit revisions do
    not flip bands and no seed sits near or above the line that routes
    deterministically to a person.
    """
    gate_limit = gate[currency]
    hard_limit = hard[currency]
    if 0.8 * gate_limit <= amount <= 1.2 * gate_limit:
        return False
    return amount < 0.8 * hard_limit


def seed_to_oracle_facts(
    seed: SeedRow,
    labels: MessageLabels,
    facts: MessageOracleFacts,
    *,
    gate_limits: dict[str, float] | None = None,
    text_only: bool = False,
) -> OracleFacts:
    """The record-facts to ``OracleFacts`` bridge (no new oracle).

    The expected outcome is derived at load time by ``oracle_outcome``,
    never stored twice. The P6 policy-version guard lives on this path:
    when gate tables are supplied, a seed whose recorded version or gate
    limit differs from the evaluated policy raises and derives nothing.
    Text-only reads (classifier training) pass ``text_only=True`` and
    skip the guard: they never feed bands to the oracle.
    """
    if not text_only:
        if gate_limits is None:
            raise ValueError("the oracle path needs the evaluated policy's gate table")
        # Seeds with no amount band (complaints, no-record, hand-written
        # probes) feed no band to the oracle, so the guard has nothing to
        # compare; banded seeds must match the evaluated table exactly
        # under its hash (raw limits are never committed).
        if seed.record_facts.amount_band is not None:
            if seed.gate_table_hash is None or seed.gate_table_hash != gate_table_hash(gate_limits):
                raise ValueError(
                    f"seed {seed.seed_key} records {seed.policy_version} "
                    f"(gate hash {seed.gate_table_hash}) but the evaluated "
                    "policy gates differ: mint a new set version (TSD-019 P6)"
                )
    amount_band = seed.record_facts.amount_band or facts.amount_band
    if amount_band not in ("under_gate", "over_gate"):
        raise ValueError(f"seed {seed.seed_key} carries unknown amount band {amount_band!r}")
    return OracleFacts(
        intent=facts.intent,
        ambiguous=facts.ambiguous,
        status=seed.record_facts.status
        if seed.kind
        in (
            "problem_transaction",
            "clean_transaction",
            "other_customer",
            "rewording",
            "hand_written",
        )
        else None,
        owner=False if seed.kind == "other_customer" else True,
        amount_band=amount_band,
        fraud_flag=seed.record_facts.fraud_flag,
        in_scope=facts.in_scope,
    )


def expected_outcome(seed: SeedRow, labels: MessageLabels, facts: MessageOracleFacts) -> str:
    """The derived outcome name, for reports: never stored on the row."""
    return oracle_outcome(seed_to_oracle_facts(seed, labels, facts, text_only=True)).value


@dataclass
class RegistryCheckReport:
    """The violations and audit notes of one registry-check run."""

    violations: list[Violation] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Whether every check is green."""
        return not self.violations


def check_duplicate_draw(seeds: list[SeedRow], record_ids: list[str | None]) -> list[Violation]:
    """No record id drawn twice in one split; no seed key twice in one registry."""
    violations: list[Violation] = []
    seen_records: dict[str, str] = {}
    for seed, record_id in zip(seeds, record_ids, strict=True):
        if record_id is None:
            continue
        if record_id in seen_records:
            violations.append(Violation("L4", f"record {record_id} drawn twice in {seed.split}"))
        else:
            seen_records[record_id] = seed.seed_key
    seen_keys: set[str] = set()
    for seed in seeds:
        if seed.seed_key in seen_keys:
            violations.append(Violation("L4", f"seed {seed.seed_key} twice in {seed.split}"))
        seen_keys.add(seed.seed_key)
    return violations


_NO_RECORD_KEYS = ("customer_id", "transcript", "complaint_text")


def check_no_records_committed(
    seeds: list[SeedRow], messages: list[MessageRow], template_texts: set[str]
) -> list[Violation]:
    """No customer records in the committed files: no raw id-shaped fields
    and no dataset template text in any message."""
    violations: list[Violation] = []
    for seed in seeds:
        dumped = seed.model_dump()
        for key in _NO_RECORD_KEYS:
            if key in dumped:
                violations.append(Violation("L3", f"seed {seed.seed_key} commits {key}"))
    normalised = {normalize_text(text) for text in template_texts}
    for message in messages:
        if normalize_text(message.message) in normalised:
            violations.append(Violation("L3", f"message {message.msg_id} copies dataset text"))
    return violations


def check_intra_set(messages: list[MessageRow], parent_of: dict[str, str]) -> list[Violation]:
    """No two messages in one split share post-normalisation text.

    A rewording must still differ from its parent (a no-op rewording
    fails); when either side normalizes empty, raw texts must differ.
    """
    violations: list[Violation] = []
    seen: dict[str, str] = {}
    for message in messages:
        normalised = normalize_text(message.message)
        if normalised and normalised in seen:
            violations.append(
                Violation("L4", f"message {message.msg_id} duplicates {seen[normalised]}")
            )
        else:
            seen.setdefault(normalised, message.msg_id)
        parent_key = parent_of.get(message.seed_key)
        if parent_key is not None:
            parent = next((m for m in messages if m.seed_key == parent_key), None)
            if parent is not None and not messages_differ(parent.message, message.message):
                violations.append(
                    Violation("L4", f"rewording {message.msg_id} is a no-op of its parent")
                )
    return violations


def messages_differ(first: str, second: str) -> bool:
    """Whether a rewording differs from its parent (raw fallback on empty)."""
    norm_first = normalize_text(first)
    norm_second = normalize_text(second)
    if not norm_first or not norm_second:
        return first != second
    return norm_first != norm_second


def check_cross_set(
    first: list[tuple[str, str]], second: list[tuple[str, str]], first_name: str, second_name: str
) -> list[Violation]:
    """No exact post-normalisation match and no Jaccard >= 0.90 pair
    between two ``(id, text)`` lists (train/test, message/gold, T-303
    checks all share this helper and name both sides in the report).
    """
    violations: list[Violation] = []
    for left_id, left_text in first:
        for right_id, right_text in second:
            norm_left = normalize_text(left_text)
            norm_right = normalize_text(right_text)
            if not norm_left or not norm_right:
                if left_text == right_text:
                    violations.append(
                        Violation(
                            "L4",
                            f"{first_name} {left_id} raw-matches {second_name} {right_id}",
                        )
                    )
                continue
            if (
                norm_left == norm_right
                or jaccard(norm_left, norm_right) >= NEAR_DUPLICATE_THRESHOLD
            ):
                violations.append(
                    Violation(
                        "L4", f"{first_name} {left_id} near-duplicates {second_name} {right_id}"
                    )
                )
    return violations


def stratum_audit(messages: list[MessageRow]) -> dict[str, dict[str, int | bool]]:
    """Per-split counts by variant and macro-outcome, flagging cells under
    30 (decision 25) and stating reviewed/unreviewed counts separately
    for every cell. Scores over unreviewed rows are never pooled with
    reviewed ones: the split is structural.
    """
    cells: dict[str, dict[str, int | bool]] = {}
    for message in messages:
        reviewed = message.provenance.review_verdict in ("pass", "corrected")
        key = f"{message.split}|{message.language_variant}|{message.oracle_facts.intent}"
        cell = cells.setdefault(key, {"n": 0, "reviewed": 0, "unreviewed": 0, "under_30": False})
        cell["n"] = int(cell["n"]) + 1
        if reviewed:
            cell["reviewed"] = int(cell["reviewed"]) + 1
        else:
            cell["unreviewed"] = int(cell["unreviewed"]) + 1
    for cell in cells.values():
        cell["under_30"] = int(cell["n"]) < 30
    return cells


def run_registry_checks(
    *,
    seeds: dict[str, list[SeedRow]],
    messages: dict[str, list[MessageRow]],
    record_ids: dict[str, list[str | None]],
    gold_hashes: set[str],
    gold_keys: set[str],
    gold_texts: list[str],
    t303_texts: list[str],
    template_texts: set[str],
    team_sources: set[str] | None = None,
) -> RegistryCheckReport:
    """L1-L5 plus the TSD-019 scans over the committed registries.

    All inputs are caller-supplied so CI runs this on synthetic fixtures
    only: the real template sets, salt and pointer log never enter the
    repo. T-303 quarantine names its check explicitly in the report.
    """
    report = RegistryCheckReport()
    sources = team_sources or {"team-brief", "hand-written"}

    hashes = {split: {seed.customer_hash for seed in rows} for split, rows in seeds.items()}
    report.violations.extend(check_l1_customer_isolation({**hashes, "gold": set(gold_hashes)}))
    dated = [
        (seed.split, date.fromisoformat(seed.event_date))
        for split in SPLITS
        for seed in seeds.get(split, [])
    ]
    report.violations.extend(check_l2_time_order(dated))
    report.violations.extend(
        check_l3_dataset_text(
            [CandidateInput(m.message, "team-brief") for rows in messages.values() for m in rows],
            template_texts,
            sources,
        )
    )
    entries = [
        SeedEntry(seed.seed_key, seed.split, seed.prompt_id)
        for split in SPLITS
        for seed in seeds.get(split, [])
    ]
    report.violations.extend(check_l4_generation_isolation(entries))
    report.violations.extend(
        check_l5_gold_held_out(
            set(gold_hashes),
            set(gold_keys),
            {seed.seed_key for seed in seeds.get("train", [])},
            {seed.seed_key for seed in seeds.get("calibration", [])},
        )
    )
    for split in SPLITS:
        report.violations.extend(
            check_duplicate_draw(seeds.get(split, []), record_ids.get(split, []))
        )
    all_seeds = [seed for split in SPLITS for seed in seeds.get(split, [])]
    all_messages = [message for split in SPLITS for message in messages.get(split, [])]
    report.violations.extend(check_no_records_committed(all_seeds, all_messages, template_texts))
    parent_of = {
        seed.seed_key: seed.parent_seed_key
        for seed in seeds.get("test", [])
        if seed.parent_seed_key is not None
    }
    for split in SPLITS:
        report.violations.extend(check_intra_set(messages.get(split, []), parent_of))

    def _pairs(rows: list[MessageRow]) -> list[tuple[str, str]]:
        return [(row.msg_id, row.message) for row in rows]

    report.violations.extend(
        check_cross_set(
            _pairs(messages.get("train", [])), _pairs(messages.get("test", [])), "train", "test"
        )
    )
    gold_rows = [(f"gold-{index}", text) for index, text in enumerate(gold_texts)]
    report.violations.extend(check_cross_set(_pairs(all_messages), gold_rows, "set", "gold"))
    t303_rows = [(f"t303-{index}", text) for index, text in enumerate(t303_texts)]
    t303_hits = check_cross_set(_pairs(all_messages), t303_rows, "set", "t303")
    for hit in t303_hits:
        report.violations.append(Violation("L4", f"T-303 quarantine: {hit.detail}"))

    audit = stratum_audit(all_messages)
    for key, cell in sorted(audit.items()):
        if cell["under_30"]:
            report.notes.append(
                f"stratum {key} n={cell['n']} "
                f"(reviewed={cell['reviewed']}, unreviewed={cell['unreviewed']}) under 30: flagged"
            )
    return report
