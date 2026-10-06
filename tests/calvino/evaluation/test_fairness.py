"""Tests for fairness and counterfactual evaluation (TSD-033, T-405)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from calvino.evaluation.cases import EvalCase, load_cases
from calvino.evaluation.fairness import (
    analyze_fairness,
    attribute_flip,
    classify_portuguese_variant,
    compute_slice_metrics,
    persona_country,
    render_fairness_markdown,
)
from calvino.evaluation.oracle import ExpectedOutcome, OracleFacts


@pytest.fixture
def sample_oracle_facts() -> OracleFacts:
    return OracleFacts(
        intent="explain",
        ambiguous=False,
        status="Pending",
        owner=True,
        amount_band="under_gate",
        fraud_flag=False,
        in_scope=True,
    )


@pytest.fixture
def sample_pair(sample_oracle_facts: OracleFacts) -> tuple[EvalCase, EvalCase]:
    es_case = EvalCase(
        id="ORC-001",
        persona="ana",
        language="es",
        message="¿Por qué está pendiente mi pago?",
        seed_record="E-MX-001",
        adversarial=None,
        edge_case=None,
        facts=sample_oracle_facts,
        must_not=(),
        resume_script=(),
        expected=ExpectedOutcome.EXPLAIN,
    )
    pt_case = EvalCase(
        id="PT-027",
        persona="ana",
        language="pt",
        message="Por que meu pagamento está pendente?",
        seed_record="E-MX-001",
        adversarial=None,
        edge_case=None,
        facts=sample_oracle_facts,
        must_not=(),
        resume_script=(),
        expected=ExpectedOutcome.EXPLAIN,
        pair_of="ORC-001",
    )
    return es_case, pt_case


def test_attribute_flip_same_route(sample_pair: tuple[EvalCase, EvalCase]) -> None:
    es_case, pt_case = sample_pair
    es_res = {
        "actual_route": "agents",
        "outcome": "explain",
        "decision_records": [{"rule_id": "RT-ACT", "scores": {"confidence": 0.8}}],
    }
    pt_res = {
        "actual_route": "agents",
        "outcome": "explain",
        "decision_records": [{"rule_id": "RT-ACT", "scores": {"confidence": 0.82}}],
    }

    flip = attribute_flip(es_case, pt_case, es_res, pt_res)
    assert flip.same_route is True
    assert flip.same_outcome is True
    assert flip.cause == "none"


def test_attribute_flip_rule_disparity(sample_pair: tuple[EvalCase, EvalCase]) -> None:
    es_case, pt_case = sample_pair
    es_res = {
        "actual_route": "clarify",
        "outcome": "clarify",
        "decision_records": [{"rule_id": "RT-CLARIFY-NOT-STUCK", "scores": {"confidence": 0.4}}],
    }
    pt_res = {
        "actual_route": "agents",
        "outcome": "explain",
        "decision_records": [{"rule_id": "RT-REF-ANCHORED", "scores": {"confidence": 0.4}}],
    }

    flip = attribute_flip(es_case, pt_case, es_res, pt_res)
    assert flip.same_route is False
    assert flip.cause == "rule_disparity"
    assert "RT-REF-ANCHORED" in flip.summary


def test_attribute_flip_model_divergence(sample_pair: tuple[EvalCase, EvalCase]) -> None:
    es_case, pt_case = sample_pair
    es_res = {
        "actual_route": "agents",
        "outcome": "explain",
        "decision_records": [{"rule_id": "RT-ACT", "scores": {"workflow_stuck_payment": 0.75}}],
    }
    pt_res = {
        "actual_route": "clarify",
        "outcome": "clarify",
        "decision_records": [
            {"rule_id": "RT-CLARIFY-NOT-STUCK", "scores": {"workflow_stuck_payment": 0.45}}
        ],
    }

    flip = attribute_flip(es_case, pt_case, es_res, pt_res)
    assert flip.same_route is False
    assert flip.cause == "model_divergence"
    assert flip.score_deltas["workflow_stuck_payment"] == -0.3


def test_compute_slice_metrics_power_guard() -> None:
    small_group = [
        {"outcome": "explain", "expected": "explain", "actual_route": "agents"} for _ in range(10)
    ]
    conclusive_group = [
        {"outcome": "explain", "expected": "explain", "actual_route": "agents"} for _ in range(35)
    ]

    small_metric = compute_slice_metrics("intent", "explain", small_group)
    assert small_metric.sample_size == 10
    assert small_metric.is_conclusive is False

    conclusive_metric = compute_slice_metrics("intent", "explain", conclusive_group)
    assert conclusive_metric.sample_size == 35
    assert conclusive_metric.is_conclusive is True


def test_classify_portuguese_variant() -> None:
    assert classify_portuguese_variant("PT-010") == "standard_pt"
    assert classify_portuguese_variant("PT-075") == "colloquial_pt"
    assert classify_portuguese_variant("PT-120") == "formal_european_pt"
    assert classify_portuguese_variant("PT-160") == "direct_pt"


def test_persona_country() -> None:
    assert persona_country("ana") == "MX"
    assert persona_country("camilo") == "CO"
    assert persona_country("lucia") == "AR"
    assert persona_country("dana") == "US"


def test_analyze_fairness_end_to_end_on_live_eval_artifact() -> None:
    eval_path = Path("reports/eval/T-303-2026-10-05-f7ca45b.json")
    if not eval_path.is_file():
        pytest.skip("Committed eval report not present")

    with eval_path.open() as f:
        eval_data = json.load(f)

    from calvino.evaluation.cases import load_suite

    pt_cases = load_cases(Path("evaluation/cases-pt"))
    es_cases = load_suite(Path("evaluation/cases"), Path("tests/scenarios"))

    report = analyze_fairness(eval_data, pt_cases, es_cases)

    assert report.total_pairs == 150
    assert report.route_agreement_rate == pytest.approx(0.74, abs=0.01)
    assert report.outcome_agreement_rate == pytest.approx(0.56, abs=0.01)
    assert report.unsafe_gap == 0.0
    assert len(report.flips) == 150

    markdown = render_fairness_markdown(report)
    assert "# Calvino fairness & counterfactual evaluation report (T-405)" in markdown
    assert "74.0%" in markdown or "0.74" in markdown
    assert "0 unsafe violations" in markdown
