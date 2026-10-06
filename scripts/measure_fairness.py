#!/usr/bin/env python3
"""CLI to generate the fairness and counterfactual evaluation report (TSD-033, T-405).

Usage:
    uv run python scripts/measure_fairness.py \
        --eval-report reports/eval/T-303-2026-10-05-f7ca45b.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from calvino.evaluation.cases import load_cases
from calvino.evaluation.fairness import analyze_fairness, render_fairness_markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract and format fairness and counterfactual metrics from an evaluation run."
    )
    parser.add_argument(
        "--eval-report",
        type=Path,
        required=True,
        help="Path to a machine-readable evaluation report JSON (T-303-*.json).",
    )
    parser.add_argument(
        "--cases-pt",
        type=Path,
        default=Path("evaluation/cases-pt"),
        help="Path to the Portuguese evaluation cases directory (default: evaluation/cases-pt).",
    )
    parser.add_argument(
        "--cases-es",
        type=Path,
        default=Path("evaluation/cases"),
        help="Path to the Spanish evaluation cases directory (default: evaluation/cases).",
    )
    parser.add_argument(
        "--scenarios-dir",
        type=Path,
        default=Path("tests/scenarios"),
        help="Path to the scenarios directory (default: tests/scenarios).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("reports/eval"),
        help="Directory to write the generated fairness report (default: reports/eval).",
    )

    args = parser.parse_args(argv)

    if not args.eval_report.is_file():
        print(f"error: evaluation report {args.eval_report} not found", file=sys.stderr)
        return 1

    with args.eval_report.open("r", encoding="utf-8") as f:
        eval_data = json.load(f)

    from calvino.evaluation.cases import load_suite

    portuguese_cases = load_cases(args.cases_pt)
    spanish_cases = load_suite(args.cases_es, args.scenarios_dir)

    report = analyze_fairness(eval_data, portuguese_cases, spanish_cases)
    md_content = render_fairness_markdown(report)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    report_base = f"T-405-{report.run_date}-{report.git_sha}"
    md_path = args.out_dir / f"{report_base}.md"
    json_path = args.out_dir / f"{report_base}.json"

    with md_path.open("w", encoding="utf-8") as f:
        f.write(md_content)

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2, sort_keys=True)

    print("Fairness report generated:")
    print(f"  Markdown: {md_path}")
    print(f"  JSON:     {json_path}")
    flips_count = len([f for f in report.flips if not f.same_route])
    matching_routes = report.total_pairs - flips_count
    msg = (
        f"Route parity: {report.route_agreement_rate:.1%} ({matching_routes}/{report.total_pairs})"
    )
    print(msg)
    print(f"Outcome parity: {report.outcome_agreement_rate:.1%}")
    print(f"Unsafe gap: {report.unsafe_gap:.1%}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
