"""Schema tests for the shared types in calvino.records: required fields, enum values, and the
rule that a raw session token never reaches the decision log."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from calvino.records import (
    DecisionRecord,
    GateVerdict,
    HumanAction,
    Route,
    Stage,
    Versions,
    session_ref_for,
)

# Synthetic test value, not a real credential.
FAKE_TOKEN = "synthetic-session-token-for-tests"


def make_record(**overrides):
    fields = {
        "stage": Stage.GATE,
        "session_ref": session_ref_for(FAKE_TOKEN),
        "policy_version": "v1",
        "verdict": GateVerdict.ALLOW,
        "latency_ms": 12.5,
    }
    fields.update(overrides)
    return DecisionRecord(**fields)


def test_enum_values_match_the_spec():
    assert [r.value for r in Route] == ["agents", "clarify", "human", "out_of_scope"]
    assert [v.value for v in GateVerdict] == ["allow", "ask", "block"]
    assert [a.value for a in HumanAction] == [
        "none",
        "approve_action",
        "request_info",
        "full_transfer",
    ]
    assert [s.value for s in Stage] == ["hard_rules", "classifier", "gate", "verifier", "human"]


def test_minimal_record_gets_defaults():
    record = make_record()
    assert record.decision_id
    assert record.timestamp.tzinfo is not None
    assert record.cost_usd == 0.0
    assert record.versions == Versions()
    assert record.verdict == "allow"


@pytest.mark.parametrize("missing", ["stage", "session_ref", "policy_version", "verdict"])
def test_required_fields(missing):
    fields = {
        "stage": Stage.GATE,
        "session_ref": session_ref_for(FAKE_TOKEN),
        "policy_version": "v1",
        "verdict": "allow",
        "latency_ms": 1.0,
    }
    del fields[missing]
    with pytest.raises(ValidationError):
        DecisionRecord(**fields)


def test_raw_session_token_is_rejected():
    with pytest.raises(ValidationError):
        make_record(session_ref=FAKE_TOKEN)


def test_session_ref_is_a_sha256_digest():
    ref = session_ref_for(FAKE_TOKEN)
    assert len(ref) == 64
    assert ref != FAKE_TOKEN
    assert ref == session_ref_for(FAKE_TOKEN)


def test_empty_token_is_refused():
    with pytest.raises(ValueError):
        session_ref_for("")


def test_unknown_stage_is_rejected():
    with pytest.raises(ValidationError):
        make_record(stage="router")


def test_unknown_field_is_rejected():
    with pytest.raises(ValidationError):
        make_record(session_token=FAKE_TOKEN)


def test_naive_timestamp_is_rejected():
    with pytest.raises(ValidationError):
        make_record(timestamp=datetime(2026, 10, 2, 12, 0, 0))


def test_aware_timestamp_is_kept():
    when = datetime(2026, 10, 2, 12, 0, 0, tzinfo=UTC)
    assert make_record(timestamp=when).timestamp == when


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_scores_must_be_finite(bad):
    with pytest.raises(ValidationError):
        make_record(scores={"needs_human": bad})


@pytest.mark.parametrize("field", ["latency_ms", "cost_usd"])
def test_negative_measurements_are_rejected(field):
    with pytest.raises(ValidationError):
        make_record(**{field: -1})


def test_records_are_immutable():
    record = make_record()
    with pytest.raises(ValidationError):
        record.verdict = "block"
