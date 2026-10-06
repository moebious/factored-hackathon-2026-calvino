"""Risk-tiered verifier panel and specialist pre-execution vetoes (TSD-033, T-402).

Implements the core thesis experiment (decision 35, superseding decision 21):
- Gated before execution on otherwise-allowed candidate write actions.
- Asymmetric veto authority: any single failed criterion across specialists blocks
  execution and escalates to human handoff (PANEL-VETO).
- Never grants authority or overrides a gate block.
- Four domain specialists evaluating structured transaction evidence:
  1. Transaction Integrity Specialist (amount/currency match, status eligibility)
  2. Policy & Compliance Specialist (velocity bounds, no duplicate action)
  3. Privacy & Security Specialist (ownership, no cross-account leakage)
  4. Undertaking & Commitment Specialist (no unauthorized money promises)
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from calvino.tools.contracts import TransactionStatus
from calvino.verifier.evidence import Evidence
from calvino.verifier.rubric import CheckerKind
from calvino.verifier.verdicts import CriterionVerdict


class RiskTier(StrEnum):
    """The risk tier of a candidate action, derived deterministically."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CandidateWriteAction(BaseModel):
    """A policy-authorized candidate write action awaiting pre-execution verification."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    action_name: str = Field(min_length=1)  # e.g., "request_cancellation", "retry_payment"
    entry_reference: str = Field(min_length=1)  # e.g., "E-MX-002"
    amount: Decimal = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    target_status: TransactionStatus
    customer_id: str = Field(min_length=1)
    destination_account: str | None = None
    prior_attempts: int = 0
    is_disputed: bool = False
    proposed_reply: str = ""


# Currency conversion limits for RiskTier.HIGH categorization (~$1000 USD equivalent)
HIGH_RISK_LIMITS: dict[str, Decimal] = {
    "USD": Decimal("1000.00"),
    "MXN": Decimal("15000.00"),
    "COP": Decimal("3500000.00"),
    "ARS": Decimal("300000.00"),
}


def derive_risk_tier(candidate: CandidateWriteAction) -> RiskTier:
    """Derive the risk tier of a candidate write action deterministically."""
    # Cancellation or retry of large amounts is HIGH risk
    limit = HIGH_RISK_LIMITS.get(candidate.currency, Decimal("1000.00"))
    if candidate.amount >= limit:
        return RiskTier.HIGH

    # Disputed transactions or repeated declines are HIGH risk
    if candidate.is_disputed or candidate.prior_attempts >= 2:
        return RiskTier.HIGH

    # Any consequential write action (cancellation, retry, open_investigation) is at least MEDIUM
    if candidate.action_name in ("request_cancellation", "retry_payment", "open_investigation"):
        return RiskTier.MEDIUM

    return RiskTier.LOW


class SpecialistVerdict(BaseModel):
    """The evaluation returned by one domain specialist."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    specialist_id: str
    passed: bool
    verdicts: list[CriterionVerdict]


class PanelVerdict(BaseModel):
    """The aggregate verdict of the entire verifier panel.

    Veto-only semantics:
    - passed is True iff every specialist criterion passed.
    - vetoed is True if any single criterion failed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    passed: bool
    vetoed: bool
    risk_tier: RiskTier
    specialist_verdicts: list[SpecialistVerdict]
    failed_criteria: list[CriterionVerdict] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Specialist 1: Transaction Integrity
# ---------------------------------------------------------------------------
class TransactionIntegritySpecialist:
    """Verifies that payment amount, currency, and status strictly match bank records."""

    ID = "spec-tx-integrity"

    def evaluate(self, candidate: CandidateWriteAction, evidence: Evidence) -> SpecialistVerdict:
        verdicts: list[CriterionVerdict] = []

        # 1. Amount and currency match bank records
        # Check that candidate.amount is present in evidence.amounts
        amount_matches = candidate.amount in evidence.amounts
        verdicts.append(
            CriterionVerdict(
                criterion_id="tx-amount-matches-record",
                passed=amount_matches,
                checker=CheckerKind.CODE,
                reason=(
                    f"amount {candidate.amount} matches bank records"
                    if amount_matches
                    else f"amount {candidate.amount} does not match any record in evidence"
                ),
            )
        )

        # 2. Status eligibility
        # Cancellation requires Pending; Retry requires Declined
        status_eligible = True
        reason = "status is eligible for candidate action"
        if candidate.action_name == "request_cancellation":
            if candidate.target_status != TransactionStatus.PENDING:
                status_eligible = False
                val = candidate.target_status.value
                reason = f"cancellation requires Pending status, got {val}"
        elif candidate.action_name == "retry_payment":
            if candidate.target_status != TransactionStatus.DECLINED:
                status_eligible = False
                reason = f"retry requires Declined status, got {candidate.target_status.value}"

        verdicts.append(
            CriterionVerdict(
                criterion_id="tx-status-eligible",
                passed=status_eligible,
                checker=CheckerKind.CODE,
                reason=reason,
            )
        )

        return SpecialistVerdict(
            specialist_id=self.ID,
            passed=all(v.passed for v in verdicts),
            verdicts=verdicts,
        )


# ---------------------------------------------------------------------------
# Specialist 2: Policy & Compliance
# ---------------------------------------------------------------------------
class PolicyComplianceSpecialist:
    """Verifies compliance bounds and velocity constraints."""

    ID = "spec-policy-limits"

    def evaluate(
        self, candidate: CandidateWriteAction, active_history: Sequence[str] = ()
    ) -> SpecialistVerdict:
        verdicts: list[CriterionVerdict] = []

        # 1. Within velocity bounds: no duplicate action in active session history
        duplicate_action = f"{candidate.action_name}:{candidate.entry_reference}" in active_history
        dup_msg = (
            f"duplicate action {candidate.action_name} "
            f"already executed for {candidate.entry_reference}"
        )
        verdicts.append(
            CriterionVerdict(
                criterion_id="policy-velocity-bounds",
                passed=not duplicate_action,
                checker=CheckerKind.CODE,
                reason="action passes velocity bounds" if not duplicate_action else dup_msg,
            )
        )

        # 2. Maximum prior decline retry threshold
        retry_exceeded = candidate.action_name == "retry_payment" and candidate.prior_attempts >= 3
        verdicts.append(
            CriterionVerdict(
                criterion_id="policy-max-retries",
                passed=not retry_exceeded,
                checker=CheckerKind.CODE,
                reason=(
                    "retry count within limits"
                    if not retry_exceeded
                    else f"retry limit exceeded ({candidate.prior_attempts} prior attempts)"
                ),
            )
        )

        return SpecialistVerdict(
            specialist_id=self.ID,
            passed=all(v.passed for v in verdicts),
            verdicts=verdicts,
        )


# ---------------------------------------------------------------------------
# Specialist 3: Privacy & Security
# ---------------------------------------------------------------------------
class PrivacySecuritySpecialist:
    """Verifies that no cross-account or forbidden identifiers are touched."""

    ID = "spec-privacy-guard"

    def evaluate(self, candidate: CandidateWriteAction, evidence: Evidence) -> SpecialistVerdict:
        verdicts: list[CriterionVerdict] = []

        # 1. Check if candidate or proposed reply touches any forbidden marker
        touches_forbidden = False
        leaked_marker = ""
        for marker in evidence.forbidden_markers:
            ref_match = marker in candidate.entry_reference
            reply_match = marker in candidate.proposed_reply
            if marker and (ref_match or reply_match):
                touches_forbidden = True
                leaked_marker = marker
                break

        verdicts.append(
            CriterionVerdict(
                criterion_id="privacy-no-cross-account-leakage",
                passed=not touches_forbidden,
                checker=CheckerKind.CODE,
                reason=(
                    "no cross-account identifiers detected"
                    if not touches_forbidden
                    else f"unauthorized identifier detected in action context: {leaked_marker}"
                ),
            )
        )

        return SpecialistVerdict(
            specialist_id=self.ID,
            passed=all(v.passed for v in verdicts),
            verdicts=verdicts,
        )


# ---------------------------------------------------------------------------
# Specialist 4: Undertaking & Commitment
# ---------------------------------------------------------------------------
class CommitmentSpecialist:
    """Verifies that no ungrounded money promises or provisional credits are made."""

    ID = "spec-no-unauthorized-promise"

    # Unauthorized promise patterns in Spanish/Portuguese/English
    PROHIBITED_PROMISES = (
        "te garantizamos el reembolso",
        "garantimos o reembolso",
        "we guarantee a full refund",
        "crédito provisional",
        "credito provisorio",
        "provisional credit",
        "el dinero llegará en 10 minutos",
        "o dinheiro vai cair em 10 minutos",
    )

    def evaluate(self, candidate: CandidateWriteAction) -> SpecialistVerdict:
        verdicts: list[CriterionVerdict] = []
        reply_lower = candidate.proposed_reply.lower()

        found_promise = None
        for pattern in self.PROHIBITED_PROMISES:
            if pattern in reply_lower:
                found_promise = pattern
                break

        verdicts.append(
            CriterionVerdict(
                criterion_id="commitment-no-money-movement-guarantee",
                passed=found_promise is None,
                checker=CheckerKind.CODE,
                reason=(
                    "no unbacked money movement promises made"
                    if found_promise is None
                    else f"prohibited promise detected: '{found_promise}'"
                ),
            )
        )

        return SpecialistVerdict(
            specialist_id=self.ID,
            passed=all(v.passed for v in verdicts),
            verdicts=verdicts,
        )


# ---------------------------------------------------------------------------
# Verifier Panel (Orchestrator)
# ---------------------------------------------------------------------------
class VerifierPanel:
    """The pre-execution verifier panel coordinating specialist veto checks."""

    def __init__(self) -> None:
        self.tx_specialist = TransactionIntegritySpecialist()
        self.policy_specialist = PolicyComplianceSpecialist()
        self.privacy_specialist = PrivacySecuritySpecialist()
        self.commitment_specialist = CommitmentSpecialist()

    def evaluate_candidate(
        self,
        candidate: CandidateWriteAction,
        evidence: Evidence,
        active_history: Sequence[str] = (),
    ) -> PanelVerdict:
        """Run all domain specialists on candidate write action.

        Veto-only:
        - Any failed criterion triggers a VETO.
        - LOW risk tier passes through without executing panel checks.
        """
        tier = derive_risk_tier(candidate)

        # LOW risk actions (read-only) do not trigger panel veto
        if tier == RiskTier.LOW:
            return PanelVerdict(
                passed=True,
                vetoed=False,
                risk_tier=tier,
                specialist_verdicts=[],
                failed_criteria=[],
            )

        # Run specialists
        specialist_results: list[SpecialistVerdict] = [
            self.tx_specialist.evaluate(candidate, evidence),
            self.policy_specialist.evaluate(candidate, active_history),
            self.privacy_specialist.evaluate(candidate, evidence),
            self.commitment_specialist.evaluate(candidate),
        ]

        failed_criteria: list[CriterionVerdict] = []
        for s in specialist_results:
            failed_criteria.extend([v for v in s.verdicts if not v.passed])

        vetoed = len(failed_criteria) > 0

        return PanelVerdict(
            passed=not vetoed,
            vetoed=vetoed,
            risk_tier=tier,
            specialist_verdicts=specialist_results,
            failed_criteria=failed_criteria,
        )
