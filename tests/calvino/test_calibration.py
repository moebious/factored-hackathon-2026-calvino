"""Tests for Laya calibration (TSD-005): metrics, temperature fitting, report and script.

The fixture is synthetic ES/PT data with deliberate over-confidence, so fitting
a temperature must measurably improve ECE on it.
"""

import csv
import importlib.util
from pathlib import Path

import pytest

from calvino.classifiers.calibration import (
    CSV_COLUMNS,
    CalibrationReport,
    Calibrator,
    calculate_brier_score,
    calculate_ece,
    fit_temperature,
    reliability_svg,
    scale_probabilities,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "calibration_synthetic.csv"


def test_calculate_ece_lower_when_better_calibrated():
    """ECE is lower when predictions match accuracy better."""
    labels = [1] * 5 + [0] * 5  # 50% accuracy either way
    ece_over = calculate_ece([0.9] * 10, labels)
    ece_better = calculate_ece([0.55] * 10, labels)
    assert ece_better < ece_over


def test_calculate_ece_poor_calibration():
    """ECE is high when predictions disagree with accuracy."""
    ece = calculate_ece([0.1] * 10, [1] * 10)
    assert ece > 0.5


def test_calculate_ece_requires_same_length():
    with pytest.raises(ValueError, match="same length"):
        calculate_ece([0.5, 0.6], [1, 0, 1])


def test_calculate_ece_handles_empty_input():
    assert calculate_ece([], []) == 0.0


def test_calculate_brier_score_perfect_predictions():
    assert calculate_brier_score([1.0, 1.0, 0.0, 0.0], [1, 1, 0, 0]) < 0.01


def test_calculate_brier_score_worst_case():
    assert calculate_brier_score([0.0, 0.0, 1.0, 1.0], [1, 1, 0, 0]) > 0.9


def test_calculate_brier_score_requires_same_length():
    with pytest.raises(ValueError, match="same length"):
        calculate_brier_score([0.5, 0.6], [1, 0, 1])


def test_calculate_brier_score_handles_empty_input():
    assert calculate_brier_score([], []) == 0.0


def test_fit_temperature_returns_reasonable_value():
    temp = fit_temperature([2.0, 3.0, -1.0, -2.0, 1.0, -0.5], [1, 1, 0, 0, 1, 0])
    assert 0.25 <= temp <= 8.0


def test_fit_temperature_handles_insufficient_data():
    assert fit_temperature([1.0], [1]) == 1.0


def test_scale_probabilities_pulls_toward_half_with_high_temperature():
    """T > 1 pulls over-confident probabilities toward 0.5."""
    scaled = scale_probabilities([0.9, 0.1], 2.0)
    assert 0.5 < scaled[0] < 0.9
    assert 0.1 < scaled[1] < 0.5


def _write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for prob, label in rows:
            writer.writerow(
                {
                    "message": "mensaje sintético",
                    "lang": "es-MX",
                    "question_type": "choice",
                    "option_count": "2",
                    "question": "needs_human",
                    "option": "human needed",
                    "predicted_prob": str(prob),
                    "label": str(label),
                }
            )


def test_calibrator_fit_and_evaluate_applies_temperature(tmp_path):
    """fit_and_evaluate actually fits and applies a temperature."""
    csv_path = tmp_path / "calibration.csv"
    # Over-confident: predicts 0.8 but only 60% of labels are 1.
    _write_csv(csv_path, [(0.8, 1)] * 6 + [(0.8, 0)] * 4)

    report = Calibrator().fit_and_evaluate(csv_path)

    assert report.n_samples == 10
    assert len(report.groups) == 1
    group = report.groups[0]
    assert group.temperature > 1.0  # over-confidence needs T > 1
    assert report.ece_after < report.ece_before
    assert report.brier_after <= report.brier_before
    assert report.temperatures() == {("choice", 2): group.temperature}


def test_calibrator_groups_by_question_type_and_option_count(tmp_path):
    """One temperature is fit per (question type, option count) group."""
    csv_path = tmp_path / "groups.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for qtype, k, prob, label in [
            ("choice", 2, 0.9, 1),
            ("choice", 2, 0.9, 0),
            ("choice", 5, 0.7, 1),
            ("choice", 5, 0.7, 1),
        ]:
            writer.writerow(
                {
                    "message": "m",
                    "lang": "pt-BR",
                    "question_type": qtype,
                    "option_count": str(k),
                    "question": "q",
                    "option": "o",
                    "predicted_prob": str(prob),
                    "label": str(label),
                }
            )

    report = Calibrator().fit_and_evaluate(csv_path)

    assert {(g.question_type, g.option_count) for g in report.groups} == {
        ("choice", 2),
        ("choice", 5),
    }
    assert report.n_samples == 4


def test_calibrator_handles_empty_csv(tmp_path):
    csv_path = tmp_path / "empty.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=CSV_COLUMNS).writeheader()

    report = Calibrator().fit_and_evaluate(csv_path)
    assert report.n_samples == 0
    assert report.ece_before == 0.0
    assert report.groups == []


def test_calibrator_rejects_missing_columns(tmp_path):
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("question,option,predicted_prob,label\nq,o,0.8,1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing columns"):
        Calibrator().fit_and_evaluate(csv_path)


def test_fixture_is_overconfident_and_improves_after_fitting():
    """On the synthetic ES/PT fixture, fitting must improve pooled ECE."""
    report = Calibrator().fit_and_evaluate(FIXTURE)

    assert isinstance(report, CalibrationReport)
    assert report.n_samples == 44
    assert report.ece_before > 0.15  # deliberately over-confident fixture
    assert report.ece_after < report.ece_before
    assert report.brier_after <= report.brier_before
    assert all(g.temperature > 1.0 for g in report.groups)


def test_reliability_svg_contains_expected_elements():
    svg = reliability_svg([0.9, 0.9, 0.2, 0.2], [1, 0, 0, 0], title="Test plot")
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    assert "<rect" in svg  # at least one accuracy bar
    assert "Test plot" in svg


def test_calibrator_writes_plot_file(tmp_path):
    out = tmp_path / "nested" / "reliability.svg"
    Calibrator().write_reliability_plot(FIXTURE, out, title="Calvino synthetic")
    assert out.exists()
    assert "<svg" in out.read_text(encoding="utf-8")


def test_run_calibration_script_end_to_end(tmp_path):
    """scripts/run_calibration.py writes reliability.svg and summary.json."""
    script = Path(__file__).resolve().parents[2] / "scripts" / "run_calibration.py"
    spec = importlib.util.spec_from_file_location("run_calibration", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    out_dir = tmp_path / "reports"
    assert module.main(["--csv", str(FIXTURE), "--out", str(out_dir)]) == 0

    svg = out_dir / "reliability.svg"
    summary = out_dir / "summary.json"
    assert svg.exists() and "<svg" in svg.read_text(encoding="utf-8")
    assert summary.exists()
    parsed = CalibrationReport.model_validate_json(summary.read_text(encoding="utf-8"))
    assert parsed.n_samples == 44
    assert parsed.ece_after < parsed.ece_before
