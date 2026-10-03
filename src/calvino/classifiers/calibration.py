"""Calibration tooling for Laya's probabilities (TSD-005).

Temperature scaling fits one parameter per (question type, option count) on a
calibration split only, never on the test split. Metrics are ECE (Expected
Calibration Error) and Brier score, reported before and after scaling, and a
reliability plot is written to a file (a hand-rolled SVG: no plotting
dependency for a hackathon-scale report).

laya 0.3.x exposes calibrated ``answer_confidence`` out of the box; this module
is Calvino's own measurement of that calibration on our synthetic ES/PT set,
per the TSD-005 acceptance criteria. Rows are binary events: "the option the
model chose (with probability ``predicted_prob``) is the correct one".
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from pydantic import BaseModel

# Columns of a calibration CSV. `message` and `lang` are provenance (the
# synthetic ES/PT text and its language); fitting uses the last four columns.
CSV_COLUMNS = [
    "message",
    "lang",
    "question_type",
    "option_count",
    "question",
    "option",
    "predicted_prob",
    "label",
]


class GroupCalibration(BaseModel):
    """Calibration result for one (question type, option count) group."""

    question_type: str
    option_count: int
    n_samples: int
    temperature: float
    ece_before: float
    ece_after: float
    brier_before: float
    brier_after: float


class CalibrationReport(BaseModel):
    """Overall calibration result: per-group temperatures plus pooled metrics."""

    n_samples: int
    ece_before: float
    ece_after: float
    brier_before: float
    brier_after: float
    groups: list[GroupCalibration]

    def temperatures(self) -> dict[tuple[str, int], float]:
        """The fitted temperature per (question type, option count)."""
        return {(g.question_type, g.option_count): g.temperature for g in self.groups}


def read_calibration_rows(path: Path) -> list[dict]:
    """Read and validate a calibration CSV (see CSV_COLUMNS for the schema)."""
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        missing = [c for c in CSV_COLUMNS if c not in reader.fieldnames]
        if missing:
            raise ValueError(f"calibration CSV {path} is missing columns: {missing}")
        return list(reader)


def calculate_ece(predicted_probs: list[float], labels: list[int], n_bins: int = 10) -> float:
    """Expected Calibration Error: weighted mean |accuracy - confidence| per bin.

    Lower is better; perfect calibration is 0.
    """
    if len(predicted_probs) != len(labels):
        raise ValueError("predicted_probs and labels must have the same length")
    if len(predicted_probs) == 0:
        return 0.0

    predicted = np.array(predicted_probs)
    labels_arr = np.array(labels)

    bins = np.linspace(0, 1, n_bins + 1)
    binids = np.clip(np.digitize(predicted, bins) - 1, 0, n_bins - 1)

    ece = 0.0
    for i in range(n_bins):
        mask = binids == i
        if mask.sum() > 0:
            acc = labels_arr[mask].mean()
            conf = predicted[mask].mean()
            ece += mask.sum() / len(predicted) * abs(acc - conf)
    return float(ece)


def calculate_brier_score(predicted_probs: list[float], labels: list[int]) -> float:
    """Brier score: mean squared error between probabilities and binary labels."""
    if len(predicted_probs) != len(labels):
        raise ValueError("predicted_probs and labels must have the same length")
    if len(predicted_probs) == 0:
        return 0.0

    predicted = np.array(predicted_probs)
    labels_arr = np.array(labels, dtype=float)
    return float(((predicted - labels_arr) ** 2).mean())


def _logit(p: float) -> float:
    """Binary logit with clipping so p=0 or p=1 stay finite."""
    p = min(max(p, 1e-6), 1 - 1e-6)
    return float(np.log(p / (1 - p)))


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-z))


def scale_probabilities(predicted_probs: list[float], temperature: float) -> list[float]:
    """Apply temperature scaling: sigmoid(logit(p) / T)."""
    logits = np.array([_logit(p) for p in predicted_probs])
    return [float(x) for x in _sigmoid(logits / temperature)]


def fit_temperature(logits: list[float], labels: list[int]) -> float:
    """Fit one temperature by grid-searching the binary cross-entropy minimum.

    The grid reaches 8.0: an over-confident model on a small set can need a
    large T before scaled probabilities match the observed accuracy.
    """
    if len(logits) != len(labels):
        raise ValueError("logits and labels must have the same length")
    if len(logits) < 2:
        return 1.0  # not enough data to fit

    logits_arr = np.array(logits, dtype=float)
    labels_arr = np.array(labels, dtype=float)

    best_temp = 1.0
    best_loss = float("inf")
    eps = 1e-7
    for temp in np.linspace(0.25, 8.0, 156):  # step 0.05
        probs = np.clip(_sigmoid(logits_arr / temp), eps, 1 - eps)
        loss = -(labels_arr * np.log(probs) + (1 - labels_arr) * np.log(1 - probs)).mean()
        if loss < best_loss:
            best_loss = loss
            best_temp = float(temp)
    return best_temp


def reliability_svg(
    predicted_probs: list[float],
    labels: list[int],
    n_bins: int = 10,
    title: str = "Reliability diagram",
) -> str:
    """Render a reliability diagram as a standalone SVG string.

    Bars are the observed accuracy per confidence bin; the diagonal is perfect
    calibration. Hand-rolled to avoid a plotting dependency (TSD-005 only
    requires the plot to be written to a file).
    """
    size = 320
    margin = 40
    plot = size - 2 * margin
    bins = np.linspace(0, 1, n_bins + 1)
    predicted = np.array(predicted_probs)
    labels_arr = np.array(labels)
    binids = np.clip(np.digitize(predicted, bins) - 1, 0, n_bins - 1) if len(predicted) else []

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size + margin}" '
        f'height="{size + margin}" viewBox="0 0 {size + margin} {size + margin}">',
        f'<text x="{size / 2}" y="20" text-anchor="middle" font-size="14">{title}</text>',
        # Perfect-calibration diagonal.
        f'<line x1="{margin}" y1="{margin + plot}" x2="{margin + plot}" y2="{margin}" '
        'stroke="#888" stroke-dasharray="4 3"/>',
    ]
    bar_w = plot / n_bins
    for i in range(n_bins):
        mask = binids == i if len(predicted) else np.array([])
        if len(mask) and mask.sum() > 0:
            acc = float(labels_arr[mask].mean())
            x = margin + i * bar_w
            y = margin + plot - acc * plot
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w - 2:.1f}" '
                f'height="{acc * plot:.1f}" fill="#4a7dbd" opacity="0.75"/>'
            )
    parts.append(
        f'<text x="{margin + plot / 2}" y="{size + 25}" text-anchor="middle" '
        f'font-size="11">mean predicted probability</text>'
    )
    parts.append(
        f'<text x="14" y="{margin + plot / 2}" text-anchor="middle" font-size="11" '
        f'transform="rotate(-90 14 {margin + plot / 2})">observed accuracy</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


class Calibrator:
    """Fits and evaluates temperature scaling on a labelled calibration CSV.

    Usage:
        report = Calibrator().fit_and_evaluate(Path("tests/fixtures/calibration_synthetic.csv"))
        report.ece_after <= report.ece_before  # scaling never worsens the fit it was fit on
    """

    def fit_and_evaluate(self, calibration_csv: Path) -> CalibrationReport:
        """Fit one temperature per (question type, option count) and report metrics.

        Metrics are pooled over all rows as well as per group, before and after
        scaling, so a reviewer can see what the temperature bought.
        """
        rows = read_calibration_rows(calibration_csv)
        if not rows:
            return CalibrationReport(
                n_samples=0,
                ece_before=0.0,
                ece_after=0.0,
                brier_before=0.0,
                brier_after=0.0,
                groups=[],
            )

        grouped: dict[tuple[str, int], tuple[list[float], list[int]]] = {}
        for row in rows:
            key = (row["question_type"], int(row["option_count"]))
            probs, labels = grouped.setdefault(key, ([], []))
            probs.append(float(row["predicted_prob"]))
            labels.append(int(row["label"]))

        groups = []
        all_before: list[float] = []
        all_after: list[float] = []
        all_labels: list[int] = []
        for (qtype, k), (probs, labels) in sorted(grouped.items()):
            logits = [_logit(p) for p in probs]
            temp = fit_temperature(logits, labels)
            scaled = scale_probabilities(probs, temp)
            groups.append(
                GroupCalibration(
                    question_type=qtype,
                    option_count=k,
                    n_samples=len(labels),
                    temperature=temp,
                    ece_before=calculate_ece(probs, labels),
                    ece_after=calculate_ece(scaled, labels),
                    brier_before=calculate_brier_score(probs, labels),
                    brier_after=calculate_brier_score(scaled, labels),
                )
            )
            all_before.extend(probs)
            all_after.extend(scaled)
            all_labels.extend(labels)

        return CalibrationReport(
            n_samples=len(all_labels),
            ece_before=calculate_ece(all_before, all_labels),
            ece_after=calculate_ece(all_after, all_labels),
            brier_before=calculate_brier_score(all_before, all_labels),
            brier_after=calculate_brier_score(all_after, all_labels),
            groups=groups,
        )

    def write_reliability_plot(
        self, calibration_csv: Path, output_path: Path, title: str = "Reliability diagram"
    ) -> None:
        """Write the reliability diagram for the whole CSV to an SVG file."""
        rows = read_calibration_rows(calibration_csv)
        probs = [float(r["predicted_prob"]) for r in rows]
        labels = [int(r["label"]) for r in rows]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(reliability_svg(probs, labels, title=title), encoding="utf-8")
