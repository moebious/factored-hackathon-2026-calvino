"""Fit temperature scaling and report calibration metrics on a labelled CSV (TSD-005).

Usage:
    uv run python scripts/run_calibration.py \
        [--csv tests/fixtures/calibration_synthetic.csv] [--out reports/calibration]

Writes `reliability.svg` (reliability diagram) and `summary.json` (report with
per-group temperatures and before/after ECE and Brier) into --out, prints the
summary, and exits non-zero if the CSV cannot be read. The default CSV is the
synthetic ES/PT fixture; point --csv at a calibration split of real model
outputs when one exists.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as a plain script from the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from calvino.classifiers.calibration import Calibrator  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("tests/fixtures/calibration_synthetic.csv"),
        help="labelled calibration CSV",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("reports/calibration"),
        help="directory for reliability.svg and summary.json",
    )
    args = parser.parse_args(argv)

    calibrator = Calibrator()
    report = calibrator.fit_and_evaluate(args.csv)
    calibrator.write_reliability_plot(args.csv, args.out / "reliability.svg")

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")

    print(f"calibration summary ({report.n_samples} samples)")
    print(
        f"  pooled ECE:   {report.ece_before:.4f} -> {report.ece_after:.4f}"
        f"   Brier: {report.brier_before:.4f} -> {report.brier_after:.4f}"
    )
    for group in report.groups:
        print(
            f"  {group.question_type} (k={group.option_count}, n={group.n_samples}):"
            f" T={group.temperature:.2f}"
            f" ECE {group.ece_before:.4f} -> {group.ece_after:.4f}"
        )
    print(f"wrote {args.out / 'reliability.svg'} and {args.out / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
