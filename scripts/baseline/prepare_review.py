"""Prepare a separate aggregate-only T-104 review candidate, without publishing."""

from __future__ import annotations

import sys

from calvino.data.baseline_review import prepare
from calvino.data.inventory_access import InventoryError


def main() -> None:
    try:
        print(f"Staged reviewed aggregates: {prepare()}")
    except InventoryError as error:
        print(f"baseline review failed: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
