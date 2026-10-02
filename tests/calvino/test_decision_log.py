"""Tests for the append-only decision log: writer and reader round-trip, ordering, and refusal
to replay a corrupted log."""

import pytest

from calvino.decision_log import DecisionLog, read_records
from calvino.records import DecisionRecord, GateVerdict, Route, Stage, Versions, session_ref_for

# Synthetic test value, not a real credential.
REF = session_ref_for("synthetic-session-token-for-tests")


def record(verdict, stage=Stage.CLASSIFIER, **extra):
    return DecisionRecord(
        stage=stage,
        session_ref=REF,
        policy_version="v1",
        verdict=verdict,
        latency_ms=3.0,
        **extra,
    )


def test_round_trip_preserves_every_field(tmp_path):
    original = record(
        Route.AGENTS,
        inputs_summary={"workflow": "stuck_payment", "amount_band": "low", "redacted": True},
        scores={"needs_human": 0.12, "clear": 0.81},
        rule_id="HR-AMOUNT",
        cost_usd=0.0004,
        versions=Versions(model="laya-multilingual", checkpoint="c1", prompt="p1", rubric="r1"),
    )
    log = DecisionLog(tmp_path / "logs" / "decisions.jsonl")
    log.append(original)
    assert list(read_records(log.path)) == [original]


def test_records_come_back_in_order(tmp_path):
    log = DecisionLog(tmp_path / "decisions.jsonl")
    written = [record(Route.CLARIFY), record(GateVerdict.ASK, Stage.GATE), record(Route.HUMAN)]
    for item in written:
        log.append(item)
    assert list(log) == written


def test_each_record_is_one_line(tmp_path):
    log = DecisionLog(tmp_path / "decisions.jsonl")
    log.append(record(Route.AGENTS))
    log.append(record(Route.HUMAN))
    assert len(log.path.read_text(encoding="utf-8").splitlines()) == 2


def test_missing_log_yields_nothing(tmp_path):
    assert list(read_records(tmp_path / "absent.jsonl")) == []


def test_blank_lines_are_skipped(tmp_path):
    log = DecisionLog(tmp_path / "decisions.jsonl")
    log.append(record(Route.AGENTS))
    with log.path.open("a", encoding="utf-8") as handle:
        handle.write("\n")
    log.append(record(Route.HUMAN))
    assert len(list(log)) == 2


def test_corrupted_line_is_reported_with_its_number(tmp_path):
    log = DecisionLog(tmp_path / "decisions.jsonl")
    log.append(record(Route.AGENTS))
    with log.path.open("a", encoding="utf-8") as handle:
        handle.write('{"not": "a record"}\n')
    with pytest.raises(ValueError, match=":2: invalid decision record"):
        list(log)
