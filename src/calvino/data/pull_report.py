"""Committed pull-report writer (TSD-019 P2 evidence, T-106).

One JSON file per pull, committed alongside the registries it
describes: considered/usable/drawn/excluded/skipped counts per split,
the manifest digest and byte ceiling inputs, the RNG seed, the policy
version, the salt version and the gate-table hash. Everything here is
offline-computable from the pull inputs and the split report: no keys,
no dataset, no salt value (the version only, never the secret).

The live pull writes ``evaluation/message-set/v1/pull-report.json``
through this writer; tests pin the shape on synthetic reports.
"""

from __future__ import annotations

import json
from pathlib import Path

from calvino.data.message_set import SALT_VERSION, SET_VERSION
from calvino.data.seed_pull import KIND_QUOTAS, NO_RECORD_NOMINAL, SplitPullReport


def pull_report_dict(
    report: SplitPullReport,
    skipped: dict[str, int],
    *,
    manifest_digest: str,
    rng_seed: int,
    policy_version: str,
    gate_table_hash: str,
) -> dict[str, object]:
    """The committed pull evidence as a plain dict (JSON-serializable)."""
    return {
        "set_version": SET_VERSION,
        "manifest_digest": manifest_digest,
        "rng_seed": rng_seed,
        "policy_version": policy_version,
        "salt_version": SALT_VERSION,
        "gate_table_hash": gate_table_hash,
        "quotas": {split: dict(kinds) for split, kinds in KIND_QUOTAS.items()},
        "nominal_no_record": dict(NO_RECORD_NOMINAL),
        "considered": dict(report.considered),
        "usable": dict(report.usable),
        "drawn": dict(report.drawn),
        "drawn_kinds": {split: dict(kinds) for split, kinds in report.drawn_kinds.items()},
        "drawn_variants": {
            split: dict(variants) for split, variants in report.drawn_variants.items()
        },
        "excluded": dict(report.excluded),
        "skipped": dict(sorted(skipped.items())),
        "usable_complaints": dict(report.usable_complaints),
        "complaint_tight": dict(report.complaint_tight),
        "pool_status_mix": {split: dict(mix) for split, mix in report.pool_status_mix.items()},
        "drawn_status_mix": {split: dict(mix) for split, mix in report.drawn_status_mix.items()},
        "notes": list(report.notes),
    }


def write_pull_report(
    path: Path,
    report: SplitPullReport,
    skipped: dict[str, int],
    *,
    manifest_digest: str,
    rng_seed: int,
    policy_version: str,
    gate_table_hash: str,
) -> Path:
    """Write the committed pull report next to the registries it describes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                pull_report_dict(
                    report,
                    skipped,
                    manifest_digest=manifest_digest,
                    rng_seed=rng_seed,
                    policy_version=policy_version,
                    gate_table_hash=gate_table_hash,
                ),
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
    return path
