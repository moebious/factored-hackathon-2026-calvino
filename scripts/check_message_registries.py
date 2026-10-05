"""Run the TSD-019 registry checks over committed registry files (T-106).

Wiring only: loads ``seeds.{split}.jsonl`` (and message files when they
exist) and runs L1-L5 plus the TSD-019 scans by id. Real registries come
later; until then the library path runs on synthetic fixtures in tests.
Fully offline: no network, no keys, no dataset, no salt.

Typical invocation once registries exist::

    uv run python scripts/check_message_registries.py \\
        --seeds-dir evaluation/message-set/v1
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from calvino.data.seed_registry import (  # noqa: E402
    load_seed_registry,
    record_ids_from_pointer_log,
    run_checks_from_files,
)

SEED_FILES = {
    "train": "seeds.train.jsonl",
    "calibration": "seeds.calibration.jsonl",
    "test": "seeds.test.jsonl",
}
MESSAGE_FILES = {
    "train": "train.jsonl",
    "calibration": "calibration.jsonl",
    "test": "test.jsonl",
}


def main(argv: list[str] | None = None) -> int:
    """Load what exists under the seeds dir and report violations."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds-dir", type=Path, default=Path("evaluation/message-set/v1"))
    parser.add_argument(
        "--pointer-log",
        type=Path,
        default=None,
        help="git-ignored seed_key -> record pointer log for the full redraw check",
    )
    args = parser.parse_args(argv)

    seed_paths = {
        split: args.seeds_dir / name
        for split, name in SEED_FILES.items()
        if (args.seeds_dir / name).exists()
    }
    if not seed_paths:
        print(f"no registry files under {args.seeds_dir}: nothing to check", file=sys.stderr)
        return 2
    for path in seed_paths.values():
        load_seed_registry(path)
    message_paths = {
        split: args.seeds_dir / name
        for split, name in MESSAGE_FILES.items()
        if (args.seeds_dir / name).exists()
    }
    record_ids = (
        record_ids_from_pointer_log(args.pointer_log) if args.pointer_log is not None else None
    )
    report = run_checks_from_files(seed_paths, message_paths or None, record_ids=record_ids)
    for violation in report.violations:
        print(f"FAILED: {violation.rule_id} {violation.detail}")
    for note in report.notes:
        print(f"note: {note}")
    print(
        f"checked {sorted(seed_paths)}: "
        f"{'PASS' if report.passed else f'{len(report.violations)} violations'}"
    )
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
