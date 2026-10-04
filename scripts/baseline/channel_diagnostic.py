"""Metadata-only manifest and separately guarded one-table channel diagnostic."""

from __future__ import annotations

import argparse
import sys

from calvino.data.baseline_channel import manifest, scan
from calvino.data.inventory_access import InventoryError, load_credentials, s3_client


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--manifest", action="store_true", help="metadata only; no object-body GET")
    mode.add_argument("--run", action="store_true", help="read calls under a reviewed byte ceiling")
    parser.add_argument("--manifest-digest", help="required for --run")
    parser.add_argument("--max-bytes", type=int, help="required for --run")
    args = parser.parse_args()
    if args.run and (not args.manifest_digest or args.max_bytes is None):
        parser.error("--run needs --manifest-digest and --max-bytes")
    if args.manifest and (args.manifest_digest or args.max_bytes is not None):
        parser.error("--manifest does not accept full-read guards")
    try:
        bucket = load_credentials()
        s3 = s3_client()
        reviewed = manifest(s3, bucket)
        if args.manifest:
            print(f"Read-only call-table manifest: {reviewed.summary()}")
        else:
            result = scan(
                s3,
                bucket,
                reviewed,
                digest=args.manifest_digest,
                max_bytes=args.max_bytes,
            )
            print(f"Staged channel aggregates: {result}")
    except InventoryError as error:
        print(f"channel diagnostic failed: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
