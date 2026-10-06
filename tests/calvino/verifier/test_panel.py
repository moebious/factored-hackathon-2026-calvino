"""Tests for the pre-execution verifier panel (TSD-033, T-402).

Validates:
- Risk tier derivation: LOW, MEDIUM, HIGH.
- Domain specialist evaluations (Transaction Integrity, Policy, Privacy, Commitment).
- Verifier panel orchestration:
  * LOW risk bypasses panel.
  * MEDIUM/HIGH risk triggers specialists.
  * Any failure triggers fail-closed VETO with structured failed criteria.
  * All pass yields passed=True, vetoed=False.
"""

from decimal import Decimal

import pytest

from calvino.tools.contracts import TransactionStatus
from calvino.verifier.evidence import Evidence
from calvino.verifier.panel import (
    CandidateWriteAction,
    RiskTier,
    VerifierPanel,
    derive_risk_tier,
)


def _sample_candidate(
    *,
    action_name: str = "request_cancellation",
    entry_reference: str = "E-MX-002",
    amount: Decimal = Decimal("5000.00"),
    currency: str = "MXN",
    target_status: TransactionStatus = TransactionStatus.PENDING,
    customer_id: str = "CUST-001",
    destination_account: str | None = None,
    prior_attempts: int = 0,
    is_disputed: bool = False,
    proposed_reply: str = "Hemos procedido con la cancelación de su transferencia.",
) -> CandidateWriteAction:
    return CandidateWriteAction(
        action_name=action_name,
        entry_reference=entry_reference,
        amount=amount,
        currency=currency,
        target_status=target_status,
        customer_id=customer_id,
        destination_account=destination_account,
        prior_attempts=prior_attempts,
        is_disputed=is_disputed,
        proposed_reply=proposed_reply,
    )


def _sample_evidence(
    *,
    amounts: tuple[Decimal, ...] = (Decimal("5000.00"),),
    forbidden_markers: tuple[str, ...] = ("ACC-OTHER-999",),
) -> Evidence:
    return Evidence(
        amounts=frozenset(amounts),
        forbidden_markers=frozenset(forbidden_markers),
        customer_language="es",
    )


class TestRiskTierDerivation:
    def test_low_risk_for_read_only(self) -> None:
        candidate = _sample_candidate(action_name="get_entry_detail", amount=Decimal("100.00"))
        assert derive_risk_tier(candidate) == RiskTier.LOW

    def test_medium_risk_for_standard_cancellation(self) -> None:
        candidate = _sample_candidate(action_name="request_cancellation", amount=Decimal("5000.00"))
        assert derive_risk_tier(candidate) == RiskTier.MEDIUM

    def test_high_risk_for_large_amount(self) -> None:
        # MXN threshold is 15,000.00
        candidate = _sample_candidate(
            action_name="request_cancellation", amount=Decimal("20000.00"), currency="MXN"
        )
        assert derive_risk_tier(candidate) == RiskTier.HIGH

    def test_high_risk_for_disputed_or_multiple_declines(self) -> None:
        candidate_disputed = _sample_candidate(
            action_name="request_cancellation", is_disputed=True, amount=Decimal("1000.00")
        )
        assert derive_risk_tier(candidate_disputed) == RiskTier.HIGH

        candidate_declined_retries = _sample_candidate(
            action_name="retry_payment", prior_attempts=2, amount=Decimal("500.00")
        )
        assert derive_risk_tier(candidate_declined_retries) == RiskTier.HIGH


class TestVerifierPanelOrchestration:
    @pytest.fixture
    def panel(self) -> VerifierPanel:
        return VerifierPanel()

    def test_clean_candidate_passes_all_specialists(self, panel: VerifierPanel) -> None:
        candidate = _sample_candidate(amount=Decimal("5000.00"))
        evidence = _sample_evidence(amounts=(Decimal("5000.00"),))

        verdict = panel.evaluate_candidate(candidate, evidence)
        assert verdict.passed is True
        assert verdict.vetoed is False
        assert len(verdict.failed_criteria) == 0
        assert verdict.risk_tier == RiskTier.MEDIUM

    def test_amount_mismatch_triggers_tx_integrity_veto(self, panel: VerifierPanel) -> None:
        # Candidate claims 5000.00, evidence only has 4500.00
        candidate = _sample_candidate(amount=Decimal("5000.00"))
        evidence = _sample_evidence(amounts=(Decimal("4500.00"),))

        verdict = panel.evaluate_candidate(candidate, evidence)
        assert verdict.passed is False
        assert verdict.vetoed is True
        failed_ids = {v.criterion_id for v in verdict.failed_criteria}
        assert "tx-amount-matches-record" in failed_ids

    def test_ineligible_status_triggers_veto(self, panel: VerifierPanel) -> None:
        # Cancelling a transaction that is already Completed or Declined
        candidate = _sample_candidate(
            action_name="request_cancellation", target_status=TransactionStatus.DECLINED
        )
        evidence = _sample_evidence()

        verdict = panel.evaluate_candidate(candidate, evidence)
        assert verdict.passed is False
        assert verdict.vetoed is True
        failed_ids = {v.criterion_id for v in verdict.failed_criteria}
        assert "tx-status-eligible" in failed_ids

    def test_duplicate_action_triggers_velocity_veto(self, panel: VerifierPanel) -> None:
        candidate = _sample_candidate()
        evidence = _sample_evidence()
        history = ["request_cancellation:E-MX-002"]

        verdict = panel.evaluate_candidate(candidate, evidence, active_history=history)
        assert verdict.passed is False
        assert verdict.vetoed is True
        failed_ids = {v.criterion_id for v in verdict.failed_criteria}
        assert "policy-velocity-bounds" in failed_ids

    def test_forbidden_identifier_triggers_privacy_veto(self, panel: VerifierPanel) -> None:
        candidate = _sample_candidate(
            proposed_reply="Transferencia realizada para la cuenta ACC-OTHER-999."
        )
        evidence = _sample_evidence(forbidden_markers=("ACC-OTHER-999",))

        verdict = panel.evaluate_candidate(candidate, evidence)
        assert verdict.passed is False
        assert verdict.vetoed is True
        failed_ids = {v.criterion_id for v in verdict.failed_criteria}
        assert "privacy-no-cross-account-leakage" in failed_ids

    def test_unauthorized_reimbursement_promise_triggers_commitment_veto(
        self, panel: VerifierPanel
    ) -> None:
        candidate = _sample_candidate(
            proposed_reply="No se preocupe, te garantizamos el reembolso completo hoy mismo."
        )
        evidence = _sample_evidence()

        verdict = panel.evaluate_candidate(candidate, evidence)
        assert verdict.passed is False
        assert verdict.vetoed is True
        failed_ids = {v.criterion_id for v in verdict.failed_criteria}
        assert "commitment-no-money-movement-guarantee" in failed_ids

    def test_low_risk_action_bypasses_panel(self, panel: VerifierPanel) -> None:
        candidate = _sample_candidate(action_name="get_entry_detail")
        evidence = _sample_evidence()

        verdict = panel.evaluate_candidate(candidate, evidence)
        assert verdict.passed is True
        assert verdict.vetoed is False
        assert verdict.risk_tier == RiskTier.LOW
        assert len(verdict.specialist_verdicts) == 0
