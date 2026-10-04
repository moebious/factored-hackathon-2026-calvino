"""Tests for the rubric model and loader (TSD-004): the shipped rubric and invalid files."""

import textwrap

import pytest
from pydantic import ValidationError

from calvino.verifier import (
    DEFAULT_RUBRIC_PATH,
    V1_RUBRIC_PATH,
    CheckerKind,
    Rubric,
    Severity,
    load_rubric,
)


def write_rubric(tmp_path, body: str):
    path = tmp_path / "rubric.yaml"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def test_shipped_customer_answer_rubric_loads():
    rubric = load_rubric()
    assert rubric.id == "customer-answer"
    assert rubric.version == 2
    assert rubric.output_type == "customer_answer"
    assert rubric.ref == "customer-answer@2"
    assert rubric.criteria, "the rubric must have criteria"
    assert all(criterion.severity is Severity.BLOCKING for criterion in rubric.criteria)


def test_shipped_rubric_covers_the_decision_17_criteria():
    ids = {criterion.id for criterion in load_rubric().criteria}
    assert {
        "amounts-dates-merchants-match",
        "stated-status-matches-record",
        "claimed-actions-read-back",
        "no-other-customer-data",
        "reply-in-customer-language",
        "no-money-movement-promise",
        "factual-claims-grounded",
        "question-fully-answered",
        "no-invented-policy",
        "next-step-valid-and-clear",
    } <= ids


def test_criteria_for_partitions_by_checker():
    rubric = load_rubric()
    for checker in (CheckerKind.CODE, CheckerKind.JUDGE):
        assert rubric.criteria_for(checker), f"the shipped rubric needs {checker} criteria"
    partitioned = sum(len(rubric.criteria_for(checker)) for checker in CheckerKind)
    assert partitioned == len(rubric.criteria)


def test_the_shipped_rubric_assigns_nothing_to_a_tier_without_an_implementation():
    # No real Laya checker exists (decision 40), so a criterion assigned to that tier could only
    # ever pass against a fake. v2 puts the promise check in code and grounding with the judge.
    rubric = load_rubric()
    assert rubric.criteria_for(CheckerKind.LAYA) == []
    checkers = {criterion.id: criterion.checker for criterion in rubric.criteria}
    assert checkers["no-money-movement-promise"] is CheckerKind.CODE
    assert checkers["factual-claims-grounded"] is CheckerKind.JUDGE


def test_rubric_v1_is_kept_unchanged_for_replay():
    v1 = load_rubric(V1_RUBRIC_PATH)
    assert v1.ref == "customer-answer@1"
    assert {c.id for c in v1.criteria_for(CheckerKind.LAYA)} == {
        "no-money-movement-promise",
        "factual-claims-grounded",
    }
    # Same criteria, only the checkers moved.
    assert {c.id for c in v1.criteria} == {c.id for c in load_rubric().criteria}


def test_default_path_points_at_the_shipped_rubric():
    assert DEFAULT_RUBRIC_PATH.name == "customer-answer-v2.yaml"
    assert DEFAULT_RUBRIC_PATH.exists()


def test_criterion_ids_must_be_unique(tmp_path):
    path = write_rubric(
        tmp_path,
        """
        id: r
        version: 1
        output_type: customer_answer
        criteria:
          - {id: same, text: one, checker: code, severity: blocking}
          - {id: same, text: two, checker: judge, severity: blocking}
        """,
    )
    with pytest.raises(ValidationError, match="unique"):
        load_rubric(path)


def test_unknown_checker_is_rejected(tmp_path):
    path = write_rubric(
        tmp_path,
        """
        id: r
        version: 1
        output_type: customer_answer
        criteria:
          - {id: c, text: one, checker: human, severity: blocking}
        """,
    )
    with pytest.raises(ValidationError):
        load_rubric(path)


def test_empty_criteria_are_rejected(tmp_path):
    path = write_rubric(
        tmp_path,
        """
        id: r
        version: 1
        output_type: customer_answer
        criteria: []
        """,
    )
    with pytest.raises(ValidationError):
        load_rubric(path)


def test_version_must_be_a_positive_integer(tmp_path):
    path = write_rubric(
        tmp_path,
        """
        id: r
        version: 0
        output_type: customer_answer
        criteria:
          - {id: c, text: one, checker: code, severity: blocking}
        """,
    )
    with pytest.raises(ValidationError):
        load_rubric(path)


def test_unknown_fields_are_rejected(tmp_path):
    path = write_rubric(
        tmp_path,
        """
        id: r
        version: 1
        output_type: customer_answer
        surprise: true
        criteria:
          - {id: c, text: one, checker: code, severity: blocking}
        """,
    )
    with pytest.raises(ValidationError):
        load_rubric(path)


def test_rubric_is_immutable():
    rubric = load_rubric()
    with pytest.raises(ValidationError):
        rubric.version = 2  # type: ignore[misc]


def test_criterion_id_pattern_is_enforced():
    with pytest.raises(ValidationError):
        Rubric.model_validate(
            {
                "id": "r",
                "version": 1,
                "output_type": "customer_answer",
                "criteria": [
                    {"id": "Bad ID", "text": "x", "checker": "code", "severity": "blocking"}
                ],
            }
        )
