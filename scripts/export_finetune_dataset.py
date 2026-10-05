"""Export the accepted T-106 train split as fine-tuning items (TSD-020, T-202).

``uv run python scripts/export_finetune_dataset.py --out <dir>``

Reads ``evaluation/message-set/v1/train.jsonl`` and writes ``items.jsonl`` and ``manifest.json``
into ``<dir>``. It refuses, with a non-zero exit and the offending ids, unless the leakage guard
passes: the split must be accepted in ``acceptance.json``, and share no text, key or customer
with calibration, test, the gold sheet, ``evaluation/cases/`` or any Portuguese set. A missing
comparison set fails the guard; it is never skipped. The export is a build artifact and is not
committed: upload it as a private Kaggle dataset and copy ``manifest.json`` into the run record.

Exit codes: 0 exported, 1 the leakage guard failed (nothing written), 2 usage error.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from calvino.data.finetune_export import LeakageError, export_train_split, load_guard_inputs
from calvino.evaluation.cases import load_suite

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SET_DIR = REPO_ROOT / "evaluation" / "message-set" / "v1"
DEFAULT_GOLD = REPO_ROOT / "tests" / "fixtures" / "gold" / "gold-050.jsonl"
DEFAULT_CASES = REPO_ROOT / "evaluation" / "cases"
DEFAULT_SCENARIOS = REPO_ROOT / "tests" / "scenarios"
DEFAULT_PORTUGUESE = REPO_ROOT / "evaluation" / "portuguese"


def git_sha(root: Path = REPO_ROOT) -> str:
    """The short sha the manifest travels with; ``unknown`` outside a clone."""
    try:
        done = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return done.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True, help="output directory (new files only)")
    parser.add_argument("--set-dir", type=Path, default=DEFAULT_SET_DIR)
    parser.add_argument(
        "--split-file", type=Path, default=None, help="default: <set-dir>/train.jsonl"
    )
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--cases-dir", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--scenarios-dir", type=Path, default=DEFAULT_SCENARIOS)
    parser.add_argument("--portuguese-dir", type=Path, default=DEFAULT_PORTUGUESE)
    args = parser.parse_args(argv)

    train_file = args.split_file or args.set_dir / "train.jsonl"
    if not train_file.is_file():
        print(f"error: {train_file} does not exist", file=sys.stderr)
        return 2
    cases = load_suite(args.cases_dir, args.scenarios_dir)
    inputs = load_guard_inputs(
        set_dir=args.set_dir,
        train_path=train_file,
        gold_path=args.gold,
        eval_messages=[(case.id, case.message) for case in cases],
        portuguese_dir=args.portuguese_dir,
    )
    try:
        manifest = export_train_split(inputs, args.out, git_sha())
    except LeakageError as error:
        print(error, file=sys.stderr)
        return 1
    print(f"exported {sum(manifest['roles'].values())} items to {args.out}")
    print(f"  roles: {manifest['roles']}; excluded: {manifest['excluded'] or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
