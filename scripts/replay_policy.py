#!/usr/bin/env python3
"""CLI to replay policy decisions and generate an auditable promotion scorecard (TSD-034, T-408).

Usage:
    uv run python scripts/replay_policy.py \
        --eval-report reports/eval/T-303-2026-10-05-f7ca45b.json \
        --baseline-policy policy/v3.yaml \
        --candidate-policy policy/v4.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from calvino.policy import load_policy
from calvino.policy.scorecard import evaluate_policy_replay, render_scorecard_markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Replay evaluation decision records to produce an auditable promotion scorecard."
        )
    )
    parser.add_argument(
        "--eval-report",
        type=Path,
        required=True,
        help="Path to an evaluation report JSON (reports/eval/T-303-*.json).",
    )
    parser.add_argument(
        "--baseline-policy",
        type=Path,
        default=Path("policy/v3.yaml"),
        help="Path to the baseline policy configuration (default: policy/v3.yaml).",
    )
    parser.add_argument(
        "--candidate-policy",
        type=Path,
        default=Path("policy/v4.yaml"),
        help="Path to the candidate policy configuration (default: policy/v4.yaml).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("reports/policy"),
        help="Output directory for generated scorecards (default: reports/policy).",
    )

    args = parser.parse_args(argv)

    if not args.eval_report.is_file():
        print(f"error: evaluation report {args.eval_report} not found", file=sys.stderr)
        return 1

    if not args.baseline_policy.is_file():
        print(f"error: baseline policy {args.baseline_policy} not found", file=sys.stderr)
        return 1

    if not args.candidate_policy.is_file():
        print(f"error: candidate policy {args.candidate_policy} not found", file=sys.stderr)
        return 1

    with args.eval_report.open("r", encoding="utf-8") as f:
        eval_data = json.load(f)

    base_pol = load_policy(args.baseline_policy)
    cand_pol = load_policy(args.candidate_policy)

    scorecard = evaluate_policy_replay(
        eval_results=eval_data,
        baseline_policy=base_pol,
        candidate_policy=cand_pol,
        baseline_policy_path_str=str(args.baseline_policy),
        candidate_policy_path_str=str(args.candidate_policy),
    )

    md_content = render_scorecard_markdown(scorecard)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    report_base = f"T-408-{scorecard.run_date}-{scorecard.git_sha}"
    md_path = args.out_dir / f"{report_base}.md"
    json_path = args.out_dir / f"{report_base}.json"

    with md_path.open("w", encoding="utf-8") as f:
        f.write(md_content)

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(scorecard.to_dict(), f, indent=2, sort_keys=True)

    print("Policy replay scorecard generated:")
    print(f"  Markdown: {md_path}")
    print(f"  JSON:     {json_path}")
    print(f"  Baseline:  {scorecard.baseline_policy_version} ({scorecard.baseline_policy_path})")
    print(f"  Candidate: {scorecard.candidate_policy_version} ({scorecard.candidate_policy_path})")
    print(f"  Pass rate: {scorecard.baseline_replay_pass_rate:.1%}")
    print(f"  Verdict flips: {len(scorecard.flips)}")
    print(f"  Recommendation: {scorecard.recommendation}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
