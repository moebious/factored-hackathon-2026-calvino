"""The append-only decision log (``decisions.jsonl``): a writer for ``DecisionRecord`` and a
reader that yields the records back, in order, for explanations and replay.

Each record is one JSON line. Lines are written with a single append, which the operating system
keeps whole for writes this small, so concurrent writers in one process do not interleave lines.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from calvino.records import DecisionRecord


class DecisionLog:
    """Appends decision records to a JSONL file, creating it (and its folder) on first write."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, record: DecisionRecord) -> None:
        """Write one record as a line at the end of the log."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = record.model_dump_json() + "\n"
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()

    def __iter__(self) -> Iterator[DecisionRecord]:
        return read_records(self.path)


def read_records(path: str | Path) -> Iterator[DecisionRecord]:
    """Yield every record in the log, in the order written. A missing log yields nothing.

    A line that is not a valid record raises an error naming its line number, so a corrupted log
    is never replayed silently.
    """
    log_path = Path(path)
    if not log_path.exists():
        return
    with log_path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                yield DecisionRecord.model_validate_json(line)
            except ValueError as error:
                raise ValueError(f"{log_path}:{number}: invalid decision record") from error
