#!/usr/bin/env python3
"""Report T-107's single-annotator consistency with the TSD-013 oracle.

The tool validates only maintainer-entered annotations. It never infers or
suggests values. Frozen model-prediction agreement is outside this report.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from calvino.data.labels import GoldRecord, validate_gold_record
from calvino.evaluation.oracle import OracleFacts, oracle_outcome

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLD_SHEET = ROOT / "tests" / "fixtures" / "gold" / "gold-050.jsonl"
DEFAULT_TEMPLATE = ROOT / "docs" / "templates" / "T-103-gold-outcome-annotations.csv"
DEFAULT_REPORT = ROOT / "reports" / "eval" / "T-103-gold-agreement.md"
DEFAULT_DISAGREEMENTS = ROOT / "reports" / "eval" / "T-103-gold-disagreements.md"

ANNOTATION_COLUMNS = (
    "record_status",
    "owner",
    "amount_band",
    "fraud_flag",
    "oracle_intent",
    "oracle_ambiguous",
    "oracle_in_scope",
    "human_outcome",
    "outcome_annotator",
    "outcome_labelled_at",
    "notes",
)


@dataclass(frozen=True)
class ScoredOutcome:
    """One complete, reviewed gold row and the unchanged oracle result."""

    gold_id: str
    oracle: str
    human: str
    annotator: str


@dataclass(frozen=True)
class GoldSheetRow:
    """One source line, retaining schema failures as reportable unscored rows."""

    gold_id: str
    record: GoldRecord | None
    validation_error: str | None = None


def load_gold_sheet(path: Path) -> tuple[GoldRecord, ...]:
    """Load rows without hiding schema-invalid annotations from the report."""
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as error:
            records.append(
                GoldSheetRow(
                    gold_id=f"line-{line_number}",
                    record=None,
                    validation_error=f"invalid JSON at line {line_number}: {error.msg}",
                )
            )
            continue
        gold_id = (
            data.get("gold_id", f"line-{line_number}")
            if isinstance(data, dict)
            else f"line-{line_number}"
        )
        try:
            records.append(
                GoldSheetRow(
                    gold_id=str(gold_id),
                    record=validate_gold_record(data),
                )
            )
        except (TypeError, ValueError) as error:
            records.append(
                GoldSheetRow(
                    gold_id=str(gold_id),
                    record=None,
                    validation_error=f"schema validation failed: {error}",
                )
            )
    return tuple(records)


def write_blank_annotation_template(
    records: Iterable[GoldRecord | GoldSheetRow], path: Path
) -> None:
    """Write a blank, ordered worksheet; copy no proposed annotation values."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ("gold_id", "message", "language_variant", *ANNOTATION_COLUMNS)
    with path.open("x", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for item in records:
            record = item.record if isinstance(item, GoldSheetRow) else item
            if record is None:
                continue
            row = {
                "gold_id": record.gold_id,
                "message": record.message,
                "language_variant": record.language_variant,
            }
            row.update({column: "" for column in ANNOTATION_COLUMNS})
            writer.writerow(row)


def _as_sheet_rows(
    records: Iterable[GoldRecord | GoldSheetRow],
) -> tuple[GoldSheetRow, ...]:
    """Accept typed records in unit tests and validated rows from the loader."""
    return tuple(
        record if isinstance(record, GoldSheetRow) else GoldSheetRow(record.gold_id, record)
        for record in records
    )


def _scored_outcomes(
    records: Iterable[GoldRecord | GoldSheetRow],
) -> tuple[ScoredOutcome, ...]:
    scored = []
    for row in _as_sheet_rows(records):
        record = row.record
        if record is None:
            continue
        if not record.has_complete_outcome_annotation():
            continue
        assert record.oracle_facts is not None
        assert record.human_outcome is not None
        facts = OracleFacts(**record.oracle_facts.model_dump())
        scored.append(
            ScoredOutcome(
                gold_id=record.gold_id,
                oracle=oracle_outcome(facts).value,
                human=record.human_outcome,
                annotator=record.outcome_annotator or "",
            )
        )
    return tuple(scored)


def _kappa(outcomes: tuple[ScoredOutcome, ...]) -> tuple[float | None, str]:
    """Cohen's kappa for oracle-table and maintainer outcomes, when defined."""
    n = len(outcomes)
    if n == 0:
        return None, "no complete reviewed rows"
    oracle_counts = Counter(outcome.oracle for outcome in outcomes)
    human_counts = Counter(outcome.human for outcome in outcomes)
    observed = sum(outcome.oracle == outcome.human for outcome in outcomes) / n
    expected = sum(
        oracle_counts[label] * human_counts[label]
        for label in oracle_counts.keys() | human_counts.keys()
    ) / (n * n)
    if expected == 1:
        return None, "expected agreement is 1.0, so the denominator is zero"
    return (observed - expected) / (1 - expected), ""


def _disagreement_keys(path: Path) -> set[tuple[str, str, str]]:
    """Read existing ledger keys so reruns preserve maintainer resolutions."""
    if not path.exists():
        return set()
    keys = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| gold-"):
            continue
        columns = [column.strip() for column in line.strip().strip("|").split("|")]
        if len(columns) >= 3:
            keys.add((columns[0], columns[1], columns[2]))
    return keys


def update_disagreement_log(outcomes: tuple[ScoredOutcome, ...], path: Path) -> None:
    """Add newly observed disagreements without overwriting human decisions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(
            "# T-107 gold/oracle disagreement log\n\n"
            "Single-annotator review ledger. New rows start pending; the "
            "maintainer classifies and resolves them. Rerunning the report "
            "preserves existing classifications and resolutions.\n\n"
            "Classifier labels: 18 existing labels are maintainer-only; 32 "
            "were model-drafted proposals. The proposal model name and version "
            "were not recorded. Proposals were seen before review, creating "
            "anchoring risk and reducing label independence. Do not describe "
            "these as blind or independent human annotations. Oracle facts "
            "and human outcomes remain separate maintainer-entered annotations.\n\n"
            "| gold_id | oracle_outcome | human_outcome | classification | "
            "rationale | resolution | reviewer | reviewed_at |\n"
            "|---|---|---|---|---|---|---|---|\n",
            encoding="utf-8",
        )

    existing = _disagreement_keys(path)
    additions = []
    for outcome in outcomes:
        key = (outcome.gold_id, outcome.oracle, outcome.human)
        if outcome.oracle != outcome.human and key not in existing:
            additions.append(
                f"| {outcome.gold_id} | {outcome.oracle} | {outcome.human} | "
                "pending | pending | pending | pending | pending |"
            )
            existing.add(key)
    if additions:
        with path.open("a", encoding="utf-8") as destination:
            destination.write("\n".join(additions) + "\n")


def render_report(
    records: tuple[GoldRecord | GoldSheetRow, ...],
    *,
    run_date: str,
    git_sha: str,
) -> str:
    """Render the consistency report without inventing or filling labels."""
    rows = _as_sheet_rows(records)
    scored = _scored_outcomes(rows)
    denominator = len(scored)
    matches = sum(outcome.oracle == outcome.human for outcome in scored)
    kappa, reason = _kappa(scored)
    annotators = {outcome.annotator for outcome in scored}
    if len(annotators) > 1:
        raise ValueError(
            "T-107 report requires one outcome annotator; found " + ", ".join(sorted(annotators))
        )
    annotator = next(iter(annotators), "no complete annotations")
    complete_ids = {outcome.gold_id for outcome in scored}
    unscored = [row for row in rows if row.gold_id not in complete_ids]
    labelled_count = sum(row.record is not None and row.record.is_labelled() for row in rows)
    maintainer_only_count = min(18, len(rows))
    model_drafted_count = max(0, len(rows) - maintainer_only_count)
    model_drafted_reviewed = min(
        model_drafted_count,
        max(0, labelled_count - maintainer_only_count),
    )

    lines = [
        "# T-107 gold/oracle consistency report",
        "",
        f"- Run date: {run_date}",
        f"- Git SHA: {git_sha}",
        "- Evidence: measured, single-annotator consistency with the TSD-013 "
        "oracle under nominal facts",
        f"- Outcome annotator: {annotator}",
        f"- Classifier labels complete: {labelled_count}/{len(rows)}",
        f"- Existing maintainer-only classifier labels: {maintainer_only_count}",
        f"- Model-drafted proposal rows reviewed: {model_drafted_reviewed}/{model_drafted_count}",
        f"- Gold sheet: {len(rows)} rows; scored {denominator}/{len(rows)}",
        "",
        f"Classifier-label provenance: {maintainer_only_count} existing labels "
        f"are maintainer-only; {model_drafted_count} were model-drafted proposals. "
        "The proposal model name and version were not recorded. The maintainer "
        "saw the proposals before review, creating anchoring risk and reducing "
        "label independence. Do not describe these as blind or independent "
        "human annotations. Oracle facts and human outcomes are separate "
        "maintainer-entered annotations.",
        "",
        "This is not an independent benchmark or a real-world oracle error bound. "
        "It does not measure T-106 defaults, message labels or model predictions.",
        "",
        "| Metric | Numerator | Denominator | Agreement |",
        "|---|---:|---:|---:|",
        (
            f"| Oracle outcome equals maintainer outcome | {matches} | {denominator} | "
            f"{matches / denominator:.1%} |"
            if denominator
            else "| Oracle outcome equals maintainer outcome | 0 | 0 | not defined |"
        ),
        "",
        (
            f"Cohen's kappa: {kappa:.4f} [descriptive]"
            if kappa is not None
            else f"Cohen's kappa: not defined ({reason})."
        ),
        "",
        "## Confusion matrix",
        "",
        "| Oracle outcome | Human outcome | Count |",
        "|---|---|---:|",
    ]
    confusion = Counter((outcome.oracle, outcome.human) for outcome in scored)
    if confusion:
        lines.extend(
            f"| {oracle} | {human} | {count} |"
            for (oracle, human), count in sorted(confusion.items())
        )
    else:
        lines.append("| — | — | 0 |")

    lines += ["", "## Unscored rows", ""]
    if unscored:
        lines += ["| gold_id | Missing or invalid fields |", "|---|---|"]
        for row in unscored:
            if row.record is None:
                missing = (row.validation_error or "invalid row",)
            else:
                missing = row.record.outcome_annotation_missing()
            lines.append(f"| {row.gold_id} | {', '.join(missing) or 'invalid annotation'} |")
    else:
        lines.append("None.")

    disagreements = [outcome for outcome in scored if outcome.oracle != outcome.human]
    lines += ["", "## Disagreements", ""]
    if disagreements:
        lines += [
            "| gold_id | Oracle outcome | Human outcome | Classification |",
            "|---|---|---|---|",
        ]
        lines.extend(
            f"| {outcome.gold_id} | {outcome.oracle} | {outcome.human} | "
            "pending maintainer review |"
            for outcome in disagreements
        )
        lines += ["", "Resolutions are recorded in `T-103-gold-disagreements.md`."]
    else:
        lines.append("None among scored rows.")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Validate the gold sheet and write the report and blank template."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-date", required=True, help="the report date (YYYY-MM-DD)")
    parser.add_argument("--git-sha", required=True, help="the commit reviewed by the maintainer")
    parser.add_argument("--gold-sheet", type=Path, default=DEFAULT_GOLD_SHEET)
    parser.add_argument(
        "--write-template",
        nargs="?",
        const=DEFAULT_TEMPLATE,
        type=Path,
        help="create a blank worksheet without overwriting an existing file",
    )
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--disagreements", type=Path, default=DEFAULT_DISAGREEMENTS)
    args = parser.parse_args(argv)

    records = load_gold_sheet(args.gold_sheet)
    scored = _scored_outcomes(records)
    if args.write_template is not None:
        write_blank_annotation_template(
            (row.record for row in records if row.record is not None),
            args.write_template,
        )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        render_report(records, run_date=args.run_date, git_sha=args.git_sha),
        encoding="utf-8",
    )
    update_disagreement_log(scored, args.disagreements)
    print(f"validated {len(records)} gold rows; scored {len(scored)}/{len(records)}")
    if args.write_template is not None:
        print(f"wrote blank worksheet {args.write_template}")
    print(f"wrote {args.report}")
    print(f"updated {args.disagreements}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
