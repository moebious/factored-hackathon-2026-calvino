"""Add the test supplement's rewording seeds to the test registry (TSD-019, T-106).

Offline and key-free. Picks 40 parents among the test base seeds that have
a brief, derives one fresh-key rewording seed per parent (kind
``rewording``, ``parent_seed_key`` set, facts and customer hash copied), and
appends them to ``seeds.test.jsonl`` and the git-ignored pointer log. It
refuses to run twice, so a re-run never doubles the supplement.

    uv run python scripts/add_rewording_seeds.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from calvino.data.message_briefs import build_plain_briefs  # noqa: E402
from calvino.data.seed_registry import (  # noqa: E402
    PointerEntry,
    build_rewording_seeds,
    ensure_salt,
    is_git_ignored,
    load_seed_registry,
    select_rewording_parents,
)


def load_pointers(path: Path) -> dict[str, PointerEntry]:
    """seed_key -> pointer entry from the git-ignored log."""
    entries = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                entry = PointerEntry(**json.loads(line))
                entries[entry.seed_key] = entry
    return entries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--seeds", type=Path, default=Path("evaluation/message-set/v1/seeds.test.jsonl")
    )
    parser.add_argument(
        "--pointer-log", type=Path, default=Path("data/message-set-pointers-v1.jsonl")
    )
    parser.add_argument("--salt-file", type=Path, default=Path("data/message-set-salt-v1"))
    args = parser.parse_args(argv)

    if not is_git_ignored(args.pointer_log):
        print(f"refusing: pointer log {args.pointer_log} is not git-ignored", file=sys.stderr)
        return 2
    salt = ensure_salt(args.salt_file)
    seeds = load_seed_registry(args.seeds)
    if any(seed.kind == "rewording" for seed in seeds):
        print("refusing: the test registry already has rewording seeds", file=sys.stderr)
        return 2
    pointers = load_pointers(args.pointer_log)
    eligible = {brief["seed_key"] for brief in build_plain_briefs("test", seeds).briefs}
    parents = select_rewording_parents(seeds, eligible)
    rows, new_pointers = build_rewording_seeds(parents, pointers, salt=salt)

    with args.pointer_log.open("a", encoding="utf-8") as handle:
        for entry in new_pointers:
            handle.write(json.dumps(entry.__dict__, sort_keys=True) + "\n")
    with args.seeds.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(row.model_dump_json() + "\n")
    print(f"added {len(rows)} rewording seeds to {args.seeds}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
