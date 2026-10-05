"""Tests for scripts/measure_routing.py (TSD-021): routing a labelled set under policy versions.

A scripted classifier stands in for live laya, so these run offline. The script routes through the
hub's own ``scores_from_answers`` and ``decide_route``, which is what makes the numbers it reports
the numbers the hub would produce.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from calvino.classifiers import LayaAnswer

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "measure_routing.py"
_spec = importlib.util.spec_from_file_location("measure_routing", SCRIPT)
assert _spec is not None and _spec.loader is not None
mr = importlib.util.module_from_spec(_spec)
sys.modules["measure_routing"] = mr
_spec.loader.exec_module(mr)


def answers(*, stuck=0.9, df=0.02, talk=0.01, injection=0.1, needs_human=0.8, area_conf=0.9):
    other = (1 - stuck - df) / 2

    def make(question_id, probabilities, confidence):
        chosen = max(probabilities, key=probabilities.get)
        return LayaAnswer(
            question_id=question_id,
            chosen_option=chosen,
            probabilities=probabilities,
            confidence=confidence,
        )

    return {
        "workflow_area": make(
            "workflow_area",
            {
                "stuck payment": stuck,
                "dispute or unrecognised charge": df / 2,
                "fraud or stolen access": df / 2,
                "other banking": other,
                "out of scope": other,
            },
            area_conf,
        ),
        "intent": make(
            "intent",
            {
                "check status": 1 - talk - 0.05,
                "cancel transfer": 0.01,
                "retry payment": 0.01,
                "open a case": 0.01,
                "check case status": 0.02,
                "talk to a person": talk,
            },
            0.3,  # the minimum-over-all-answers confidence (v2) is dragged down by this
        ),
        "clear_enough": make("clear_enough", {"clear": 0.05, "unclear": 0.95}, 0.95),
        "needs_human": make(
            "needs_human",
            {"human needed": needs_human, "can handle automatically": 1 - needs_human},
            0.8,
        ),
        "injection": make("injection", {"risky": injection, "not risky": 1 - injection}, 0.9),
    }


ROWS = [
    {"id": "R1", "message": "routine status", "needs_person": False, "kind": "status"},
    {"id": "R2", "message": "routine cancel", "needs_person": False, "kind": "cancel"},
    {"id": "N1", "message": "fraud report", "needs_person": True, "kind": "fraud"},
    {"id": "N2", "message": "ask for a person", "needs_person": True, "kind": "ask_person"},
]
SCRIPTED = {
    "routine status": answers(),
    "routine cancel": answers(needs_human=0.9),
    "fraud report": answers(stuck=0.05, df=0.9, needs_human=0.7),
    "ask for a person": answers(talk=0.8, needs_human=0.75),
}


def classify(text):
    return SCRIPTED[text]


def policies():
    return {v: mr.load_policy(mr.POLICY_DIR / f"{v}.yaml") for v in ("v2", "v3")}


def test_v3_frees_routine_rows_and_still_stops_the_needs_a_person_rows():
    result = mr.measure(ROWS, classify, policies())
    v2, v3 = result["policies"]["v2"], result["policies"]["v3"]
    assert v2["routine_to_agents"] == [0, 2]  # needs_human, clear_enough and confidence stop both
    assert v3["routine_to_agents"] == [2, 2]
    assert v3["needs_person_to_agents"] == [0, 2]
    assert v3["needs_person_to_human"] == [2, 2]
    assert v3["needs_person_stopped_by"] == {"RT-DISPUTE-FRAUD": 1, "RT-TALK-TO-PERSON": 1}


def test_single_signal_auroc_and_the_max_of_the_other_three():
    auroc = mr.measure(ROWS, classify, policies())["auroc"]
    # needs_human is 0.8/0.9 on routine and 0.7/0.75 on needs-a-person: ranked backwards.
    assert auroc["needs_human"] == 0.0
    assert auroc["area: dispute or fraud"] == 0.75  # one positive wins both pairs, one ties
    assert auroc["max(area, intent, injection)"] == 1.0


def test_per_row_routes_are_reported_for_every_policy():
    rows = mr.measure(ROWS, classify, policies())["rows"]
    by_id = {row["id"]: row for row in rows}
    assert by_id["R1"]["routes"] == {"v2": ["human", "RT-ESCALATE"], "v3": ["agents", "RT-ACT"]}
    assert by_id["N2"]["routes"]["v3"][1] == "RT-TALK-TO-PERSON"


def test_auroc_handles_ties_and_empty_classes():
    assert mr.auroc([0.5, 0.5], [True, False]) == 0.5
    assert mr.auroc([0.9, 0.1], [True, False]) == 1.0
    assert mr.auroc([0.9, 0.1], [False, False]) is None


def test_frozen_rows_are_refused(tmp_path):
    path = tmp_path / "rows.jsonl"
    path.write_text(
        json.dumps({"id": "T1", "message": "m", "needs_person": False, "split": "test"}) + "\n"
    )
    with pytest.raises(SystemExit, match="frozen split"):
        mr.load_rows(path)


def test_main_writes_the_report_and_the_machine_results(tmp_path):
    labels = tmp_path / "rows.jsonl"
    labels.write_text("\n".join(json.dumps(row) for row in ROWS) + "\n")
    out = tmp_path / "out"
    assert (
        mr.main(["--labels", str(labels), "--out", str(out), "--tag", "t"], classify=classify) == 0
    )
    report = next(out.glob("t-*.md")).read_text()
    assert "routine rows reaching the agent | 0/2 (0%) | 2/2 (100%)" in report
    assert "Evidence label: **exploratory, team-written rows**" in report
    payload = json.loads(next(out.glob("t-*.json")).read_text())
    assert payload["n"] == 4 and payload["needs_person"] == 2
