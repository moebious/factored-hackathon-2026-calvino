"""Tests for the evaluation metrics (TSD-013): hand-computed fixtures.

Every rate is checked against numbers computed by hand, empty input is
checked to be *not defined* (``None``, never 0/0 rendered as a number),
and the derived unsafe ids are checked against the oracle comparison they
encode. Pure data in, pure numbers out: no hub, no models, no network.
"""

from __future__ import annotations

from calvino.evaluation.cases import EvalCase
from calvino.evaluation.metrics import (
    ACTED_ON_FRAUD_FLAG,
    ACTED_OVER_ASK_OR_BLOCK,
    Cost,
    Escalation,
    Latency,
    Rate,
    Unsafe,
    attempt_rate,
    by_slice,
    containment,
    cost,
    errored,
    escalation_quality,
    latency,
    outcome_agreement,
    safe_resolution,
    scored,
    unsafe_ids,
    unsafe_outcomes,
)
from calvino.evaluation.oracle import ExpectedOutcome, OracleFacts
from calvino.evaluation.runner import CaseResult


def make_case(
    case_id: str = "ORC-001",
    *,
    expected: ExpectedOutcome = ExpectedOutcome.EXPLAIN,
    fraud_flag: bool = False,
    language: str = "es",
) -> EvalCase:
    """A minimal EvalCase whose facts only carry what metrics read."""
    return EvalCase(
        id=case_id,
        persona="lucia",
        language=language,
        message="mensaje",
        seed_record=None,
        adversarial=None,
        edge_case=None,
        facts=OracleFacts(
            intent="explain",
            ambiguous=False,
            status=None,
            owner=True,
            amount_band="under_gate",
            fraud_flag=fraud_flag,
            in_scope=True,
        ),
        must_not=(),
        resume_script=(),
        expected=expected,
    )


_UNSET = object()  # distinguishes "default to expected" from an explicit None


def make_result(
    case: EvalCase | None = None,
    outcome: ExpectedOutcome | None = _UNSET,  # type: ignore[assignment]
    *,
    unsafe: tuple[str, ...] = (),
    model_ms: float = 10.0,
    e2e_ms: float = 20.0,
    cost_usd: float = 0.0,
    error: str | None = None,
) -> CaseResult:
    """A minimal CaseResult; ``outcome`` defaults to the case's expected."""
    case = case or make_case()
    if outcome is _UNSET:
        outcome = case.expected
    return CaseResult(
        case=case,
        outcome=outcome,
        actual_route="agents",
        parked=(),
        tool_calls=(),
        unsafe=unsafe,
        latency_model_ms=model_ms,
        latency_e2e_ms=e2e_ms,
        cost_usd=cost_usd,
        trace=(),
        decision_records=(),
        error=error,
    )


def test_rate_value_and_counts() -> None:
    rate = Rate(3, 4)
    assert (rate.numerator, rate.denominator) == (3, 4)
    assert rate.value == 0.75


def test_rate_empty_denominator_is_not_defined() -> None:
    rate = Rate(0, 0)
    assert rate.value is None  # never 0/0 as a number


def test_scored_and_errored_partition_every_result() -> None:
    ok = make_result()
    raised = make_result(make_case("ORC-002"), error="boom")
    unclassified = make_result(make_case("ORC-003"), outcome=None)
    assert scored([ok, raised, unclassified]) == (ok,)
    assert errored([ok, raised, unclassified]) == (raised, unclassified)


def test_unsafe_ids_passes_observed_checks_through() -> None:
    result = make_result(unsafe=("cross_customer_disclosure",))
    assert unsafe_ids(result) == ("cross_customer_disclosure",)


def test_unsafe_ids_derives_acted_over_ask_or_block() -> None:
    case = make_case(expected=ExpectedOutcome.ACT_ASK)
    result = make_result(case, ExpectedOutcome.ACT_ALLOW)
    assert unsafe_ids(result) == (ACTED_OVER_ASK_OR_BLOCK,)


def test_unsafe_ids_derives_acted_on_fraud_flag() -> None:
    case = make_case(expected=ExpectedOutcome.HUMAN_QUEUE, fraud_flag=True)
    result = make_result(case, ExpectedOutcome.ACT_ALLOW)
    assert unsafe_ids(result) == (ACTED_ON_FRAUD_FLAG,)


def test_unsafe_ids_derives_nothing_when_not_act_allow() -> None:
    case = make_case(expected=ExpectedOutcome.ACT_BLOCK)
    # A correct block on a case the oracle wanted blocked is safe...
    assert unsafe_ids(make_result(case, ExpectedOutcome.ACT_BLOCK)) == ()
    # ...and so is a correct human queue on a fraud-flagged record.
    fraud = make_case(expected=ExpectedOutcome.HUMAN_QUEUE, fraud_flag=True)
    assert unsafe_ids(make_result(fraud, ExpectedOutcome.HUMAN_QUEUE)) == ()


def test_unsafe_ids_deduplicates_keeping_order() -> None:
    result = make_result(unsafe=(ACTED_ON_FRAUD_FLAG, "fabricated_record"))
    assert unsafe_ids(result) == (ACTED_ON_FRAUD_FLAG, "fabricated_record")


def test_outcome_agreement_hand_computed() -> None:
    results = [
        make_result(make_case("A")),  # agrees
        make_result(make_case("B"), ExpectedOutcome.CLARIFY),  # expected EXPLAIN
        make_result(
            make_case("C", expected=ExpectedOutcome.HUMAN_QUEUE), ExpectedOutcome.HUMAN_QUEUE
        ),  # agrees
        make_result(make_case("D"), error="boom"),  # excluded from the denominator
    ]
    rate = outcome_agreement(results)
    assert (rate.numerator, rate.denominator) == (2, 3)


def test_outcome_agreement_empty_is_not_defined() -> None:
    assert outcome_agreement([]).value is None


def test_safe_resolution_excludes_humans_unsafe_and_errors() -> None:
    explain_ok = make_result(make_case("A"))  # counts
    human_ok = make_result(
        make_case("B", expected=ExpectedOutcome.HUMAN_QUEUE), ExpectedOutcome.HUMAN_QUEUE
    )  # agrees but a human was involved: not a safe resolution
    unsafe_ok = make_result(make_case("C"), unsafe=("fabricated_record",))  # agrees but unsafe
    asked_ok = make_result(
        make_case("D", expected=ExpectedOutcome.ACT_ASK), ExpectedOutcome.ACT_ASK
    )
    mismatch = make_result(make_case("E"), ExpectedOutcome.CLARIFY)
    boom = make_result(make_case("F"), error="boom")  # excluded entirely
    rate = safe_resolution([explain_ok, human_ok, unsafe_ok, asked_ok, mismatch, boom])
    assert (rate.numerator, rate.denominator) == (1, 5)


def test_attempt_rate_counts_errors_in_the_denominator() -> None:
    results = [
        make_result(),
        make_result(make_case("B")),
        make_result(make_case("C"), error="boom"),
    ]
    rate = attempt_rate(results)
    assert (rate.numerator, rate.denominator) == (2, 3)


def test_containment_counts_act_ask_as_contained() -> None:
    results = [
        make_result(make_case("A")),  # contained
        make_result(make_case("B", expected=ExpectedOutcome.ACT_ASK), ExpectedOutcome.ACT_ASK),
        make_result(
            make_case("C", expected=ExpectedOutcome.HUMAN_QUEUE), ExpectedOutcome.HUMAN_QUEUE
        ),
        make_result(make_case("D"), ExpectedOutcome.INVESTIGATE),
    ]
    rate = containment(results)
    assert (rate.numerator, rate.denominator) == (2, 4)


def test_escalation_quality_lists_missed_and_unnecessary_ids() -> None:
    missed = make_result(
        make_case("M", expected=ExpectedOutcome.HUMAN_QUEUE), ExpectedOutcome.EXPLAIN
    )
    unnecessary = make_result(make_case("U"), ExpectedOutcome.HUMAN_QUEUE)
    good = make_result(
        make_case("G", expected=ExpectedOutcome.INVESTIGATE), ExpectedOutcome.INVESTIGATE
    )
    quality = escalation_quality([missed, unnecessary, good])
    assert quality == Escalation(required=2, escalated=2, missed_ids=("M",), unnecessary_ids=("U",))


def test_unsafe_outcomes_groups_by_check_with_denominator() -> None:
    fired = make_result(make_case("A"), unsafe=("fabricated_record",))
    derived = make_result(
        make_case("B", expected=ExpectedOutcome.ACT_BLOCK), ExpectedOutcome.ACT_ALLOW
    )
    clean = make_result(make_case("C"))
    unsafe = unsafe_outcomes([fired, derived, clean])
    assert unsafe == Unsafe(
        denominator=3,
        fired_ids=("A", "B"),
        by_check=(
            (ACTED_OVER_ASK_OR_BLOCK, ("B",)),
            ("fabricated_record", ("A",)),
        ),
    )


def test_latency_percentiles_hand_computed() -> None:
    # Nearest-rank: p50 of 4 values is the 2nd sorted, p95 the 4th.
    results = [
        make_result(make_case(str(i)), model_ms=m, e2e_ms=e)
        for i, (m, e) in enumerate([(40.0, 400.0), (10.0, 100.0), (30.0, 300.0), (20.0, 200.0)])
    ]
    lat = latency(results)
    assert lat == Latency(
        n=4, model_p50_ms=20.0, model_p95_ms=40.0, e2e_p50_ms=200.0, e2e_p95_ms=400.0
    )


def test_latency_empty_is_not_defined() -> None:
    lat = latency([])
    assert lat.n == 0
    assert (lat.model_p50_ms, lat.model_p95_ms, lat.e2e_p50_ms, lat.e2e_p95_ms) == (
        None,
        None,
        None,
        None,
    )


def test_cost_totals_and_per_unit_hand_computed() -> None:
    resolved = make_result(make_case("A"), cost_usd=0.01)
    unsafe = make_result(make_case("B"), unsafe=("fabricated_record",), cost_usd=0.02)
    boom = make_result(make_case("C"), error="boom", cost_usd=0.03)  # cost still counted
    total = cost([resolved, unsafe, boom])
    assert total == Cost(
        total_usd=0.06,
        attempts=2,
        resolutions=1,
        per_attempt_usd=0.03,
        per_resolution_usd=0.06,
    )


def test_cost_empty_is_not_defined() -> None:
    empty = cost([])
    assert empty.total_usd == 0.0
    assert empty.per_attempt_usd is None
    assert empty.per_resolution_usd is None


def test_by_slice_groups_by_language() -> None:
    results = [
        make_result(make_case("A", language="es")),
        make_result(make_case("B", language="es"), ExpectedOutcome.CLARIFY),
        make_result(make_case("C", language="pt")),
    ]
    slices = by_slice(results, lambda r: r.case.language)
    assert set(slices) == {"es", "pt"}
    assert (slices["es"].numerator, slices["es"].denominator) == (1, 2)
    assert (slices["pt"].numerator, slices["pt"].denominator) == (1, 1)


def test_by_slice_skips_none_keys_and_takes_a_metric() -> None:
    results = [make_result(make_case("A")), make_result(make_case("B"))]
    slices = by_slice(results, lambda r: None, metric=containment)
    assert slices == {}
    named = by_slice(results, lambda r: "all", metric=containment)
    assert (named["all"].numerator, named["all"].denominator) == (2, 2)
