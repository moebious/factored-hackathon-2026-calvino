"""Focused parsing and lineage checks for T-105 model types."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from calvino.data.freshness_models import FreshnessInputError, SourceRevision

FIXTURE_DIR = Path(__file__).parents[2] / "fixtures" / "freshness"


def _sample_row() -> dict:
    return json.loads((FIXTURE_DIR / "initial.jsonl").read_text(encoding="utf-8").splitlines()[0])


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("revision_no", 1.5),
        ("revision_no", True),
        ("record_id", None),
        ("customer_id", None),
        ("source_file_id", ""),
    ],
)
def test_source_parser_rejects_coerced_revision_and_identity_values(field, value):
    raw = _sample_row()
    raw[field] = value

    with pytest.raises(FreshnessInputError):
        SourceRevision.from_mapping(raw)


def test_revision_lineage_id_distinguishes_observed_source_files():
    original = SourceRevision.from_mapping(_sample_row())
    replayed_raw = _sample_row()
    replayed_raw["source_file_id"] = "replayed-from-another-file"
    replayed = SourceRevision.from_mapping(replayed_raw)

    assert replayed.content_sha256 == original.content_sha256
    assert replayed.source_file_sha256 != original.source_file_sha256
    assert replayed.lineage_artifact_id != original.lineage_artifact_id
