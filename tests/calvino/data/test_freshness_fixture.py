"""Schema and split checks for the synthetic T-105 freshness fixture."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from calvino.data.splits import assign_customer, assign_record

FIXTURE_DIR = Path(__file__).parents[2] / "fixtures" / "freshness"


def _jsonl(name: str) -> list[dict]:
    return [
        json.loads(line) for line in (FIXTURE_DIR / name).read_text(encoding="utf-8").splitlines()
    ]


def test_freshness_fixture_is_synthetic_and_uses_a_fixed_producer():
    manifest = json.loads((FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["synthetic"] is True
    assert manifest["producer_commit"] == "fixture-commit-v1"
    assert manifest["contract_version"] == "freshness-source-v1"
    assert manifest["frozen_suite_sentinel_id"] in manifest["frozen_members"]


def test_fixture_customer_ids_exercise_the_real_split_assigner():
    expected = {
        "SYN-FRESH-0000": "train",
        "SYN-FRESH-0001": "calibration",
        "SYN-FRESH-0002": "test",
        "SYN-FRESH-0003": "train",
        "SYN-FRESH-0006": "train",
        "SYN-FRESH-0007": "train",
    }

    assert {customer_id: assign_customer(customer_id) for customer_id in expected} == expected


def test_fixture_covers_countries_currencies_and_no_brazil():
    rows = _jsonl("initial.jsonl") + _jsonl("updates.jsonl")
    countries = {row["country_variant"] for row in rows}
    currencies = {row["payload"]["currency"] for row in rows if "currency" in row["payload"]}

    assert countries == {"MX", "CO", "AR"}
    assert currencies == {"MXN", "COP", "ARS", "USD"}
    assert all(row["country_variant"] != "BR" for row in rows)


def test_fixture_pilot_record_uses_the_real_split_rule():
    pilot = next(row for row in _jsonl("updates.jsonl") if row["record_id"] == "move-date")

    assert assign_record(pilot["customer_id"], date.fromisoformat(pilot["event_date"])) is None


def test_fixture_has_day_zero_day_thirty_and_day_thirty_one_sources():
    initial = {row["record_id"]: row for row in _jsonl("initial.jsonl")}
    day_zero = initial["arrival-day0"]
    day_thirty = initial["arrival-day30"]
    day_thirty_one = initial["arrival-day31"]

    assert (
        date.fromisoformat(day_zero["arrival_date"]) - date.fromisoformat(day_zero["process_date"])
    ).days == 0
    assert (
        date.fromisoformat(day_thirty["arrival_date"])
        - date.fromisoformat(day_thirty["process_date"])
    ).days == 30
    assert (
        date.fromisoformat(day_thirty_one["arrival_date"])
        - date.fromisoformat(day_thirty_one["process_date"])
    ).days == 31
