"""Unit tests for the policy engine (TSD-001): config, hard rules, thresholds, fail-closed
behaviour, record contents and replay. No model calls, network or dataset; all values synthetic."""

import itertools
import math

import pytest
import yaml
from pydantic import ValidationError

from calvino.decision_log import DecisionLog
from calvino.policy import (
    DEFAULT_POLICY_PATH,
    Policy,
    decide_gate,
    decide_route,
    load_policy,
    replay_decision,
)
from calvino.records import GateVerdict, HumanAction, Route, Stage, session_ref_for

REF = session_ref_for("synthetic-session-token-for-tests")


@pytest.fixture(scope="module")
def policy() -> Policy:
    return load_policy(DEFAULT_POLICY_PATH.with_name("v2.yaml"))


def facts(**overrides):
    base = {
        "session_ref": REF,
        "fraud_signal": False,
        "asks_for_human": False,
        "auth_failures": 0,
        "via_regulator": False,
        "vulnerable_customer": False,
    }
    return {**base, **overrides}


def scores(**overrides):
    """Scores that, unmodified, lead to Route.AGENTS and GateVerdict.ALLOW."""
    base = {
        "needs_human": 0.05,
        "clear_enough": 0.95,
        "confidence": 0.95,
        "workflow_out_of_scope": 0.02,
        "workflow_dispute_or_fraud": 0.02,
        "injection": 0.01,
    }
    return {**base, **overrides}


def action(**overrides):
    base = {
        "name": "retry_payment",
        "transaction_status": "declined",
        "amount": 1000.0,
        "currency": "MXN",
        "owner_verified": True,
    }
    return {**base, **overrides}


def around(threshold: float):
    """Values just below, on and just above a threshold."""
    return math.nextafter(threshold, 0), threshold, math.nextafter(threshold, 1)


# --- configuration -----------------------------------------------------------------------------


def test_shipped_policy_loads_and_is_labelled(policy):
    assert DEFAULT_POLICY_PATH.name == "v3.yaml"
    assert policy.version == "v2"
    assert "assumption" in policy.assumptions.lower()
    assert set(policy.hard_rules.amount_limit) == {"MXN", "COP", "ARS", "USD"}


def test_shipped_thresholds_are_pinned(policy):
    # A released version is immutable: changing a value means a new policy file, and this test.
    assert policy.route.model_dump() == {
        "escalate_at": 0.70,
        "act_below": 0.30,
        "out_of_scope_at": 0.60,
        "dispute_or_fraud_at": 0.50,
        "injection_at": 0.50,
        "min_clear_enough": 0.30,  # lowered from v1's 0.50 on measured laya scores (decision 30)
        "min_confidence": 0.60,
        # The v3 switches default to the v1/v2 behaviour, so a released file replays unchanged.
        "use_needs_human": True,
        "talk_to_person_at": None,
        "min_stuck_payment": None,
        "confidence_source": "min_all",
    }
    assert policy.gate.allow_amount_limit == {
        "MXN": 8500,
        "COP": 2000000,
        "ARS": 175000,
        "USD": 500,
    }
    assert policy.hard_rules.amount_limit["USD"] == 5000
    assert policy.hard_rules.auth_failure_limit == 3


def _raw():
    return yaml.safe_load(DEFAULT_POLICY_PATH.with_name("v2.yaml").read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "edit",
    [
        lambda raw: raw["route"].update(act_below=0.8),  # band inverted
        lambda raw: raw["route"].update(escalate_at=1.5),  # not a probability
        lambda raw: raw["route"].update(surprise=1),  # unknown field
        lambda raw: raw["gate"]["allow_amount_limit"].pop("USD"),  # currencies differ
        lambda raw: raw["gate"]["allow_amount_limit"].update(USD=6000),  # gate above hard limit
        lambda raw: raw["hard_rules"]["amount_limit"].update(MXN=0),
        lambda raw: raw["gate"].update(on_missing_scores="allow"),
        lambda raw: raw.update(assumptions=""),
    ],
)
def test_invalid_policy_files_are_rejected(edit):
    raw = _raw()
    edit(raw)
    with pytest.raises(ValidationError):
        Policy.model_validate(raw)


def test_load_policy_reads_another_file(tmp_path):
    raw = _raw()
    raw["version"] = "v2"
    path = tmp_path / "v2.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    assert load_policy(path).version == "v2"


# --- route: hard rules -------------------------------------------------------------------------

HARD_CASES = [
    ("HR-FRAUD", {"fraud_signal": True}),
    ("HR-AMOUNT", {"amount": 5000.01, "currency": "USD"}),
    ("HR-ASKS-HUMAN", {"asks_for_human": True}),
    ("HR-AUTH", {"auth_failures": 3}),
    ("HR-REGULATOR", {"via_regulator": True}),
    ("HR-VULNERABLE", {"vulnerable_customer": True}),
]


@pytest.mark.parametrize(("rule", "override"), HARD_CASES)
@pytest.mark.parametrize(
    "score_set",
    [scores(), scores(needs_human=0.0, clear_enough=1.0), scores(workflow_out_of_scope=1.0)],
)
def test_each_hard_rule_fires_and_wins_over_any_score(policy, rule, override, score_set):
    decision = decide_route(score_set, facts(**override), policy)
    assert decision.route is Route.HUMAN
    assert decision.human_action is HumanAction.FULL_TRANSFER
    assert decision.rule_id == rule
    assert decision.record.rule_id == rule
    assert decision.record.stage is Stage.HARD_RULES


def test_hard_rules_win_without_any_scores(policy):
    assert decide_route({}, facts(fraud_signal=True), policy).rule_id == "HR-FRAUD"


@pytest.mark.parametrize(("first", "second"), list(itertools.combinations(HARD_CASES, 2)))
def test_first_matching_hard_rule_decides(policy, first, second):
    decision = decide_route(scores(), facts(**first[1], **second[1]), policy)
    assert decision.rule_id == first[0]  # HARD_CASES is in evaluation order


def test_auth_boundary(policy):
    assert decide_route(scores(), facts(auth_failures=2), policy).rule_id == "RT-ACT"
    assert decide_route(scores(), facts(auth_failures=3), policy).rule_id == "HR-AUTH"


@pytest.mark.parametrize(("currency", "limit"), [("MXN", 85000), ("COP", 20000000), ("USD", 5000)])
def test_hard_amount_boundary_per_currency(policy, currency, limit):
    below = decide_route(scores(), facts(amount=limit - 0.01, currency=currency), policy)
    on = decide_route(scores(), facts(amount=limit, currency=currency), policy)
    above = decide_route(scores(), facts(amount=limit + 0.01, currency=currency), policy)
    assert [below.rule_id, on.rule_id, above.rule_id] == ["RT-ACT", "RT-ACT", "HR-AMOUNT"]


# --- route: thresholds -------------------------------------------------------------------------


def test_route_act_clarify_escalate_bands(policy):
    low, on_low, above_low = around(0.30)
    assert decide_route(scores(needs_human=low), facts(), policy).route is Route.AGENTS
    for needs_human in (on_low, above_low, 0.5):  # on the lower threshold goes to the safer side
        decision = decide_route(scores(needs_human=needs_human), facts(), policy)
        assert (decision.route, decision.rule_id) == (Route.CLARIFY, "RT-CLARIFY-BAND")
    below_high, on_high, _ = around(0.70)
    assert decide_route(scores(needs_human=below_high), facts(), policy).route is Route.CLARIFY
    for needs_human in (on_high, 0.99):
        decision = decide_route(scores(needs_human=needs_human), facts(), policy)
        assert (decision.route, decision.human_action) == (Route.HUMAN, HumanAction.FULL_TRANSFER)
        assert decision.rule_id == "RT-ESCALATE"


@pytest.mark.parametrize(
    ("score", "threshold", "route", "rule"),
    [
        ("confidence", 0.60, Route.CLARIFY, "RT-CLARIFY-CONFIDENCE"),
        ("clear_enough", 0.30, Route.CLARIFY, "RT-CLARIFY-UNCLEAR"),
    ],
)
def test_low_confidence_and_unclear_clarify(policy, score, threshold, route, rule):
    below, on, above = around(threshold)
    assert decide_route(scores(**{score: below}), facts(), policy).rule_id == rule
    assert decide_route(scores(**{score: on}), facts(), policy).route is Route.AGENTS
    assert decide_route(scores(**{score: above}), facts(), policy).route is Route.AGENTS
    assert decide_route(scores(**{score: below}), facts(), policy).route is route


@pytest.mark.parametrize(
    ("score", "threshold", "route", "rule"),
    [
        ("workflow_dispute_or_fraud", 0.50, Route.HUMAN, "RT-DISPUTE-FRAUD"),
        ("workflow_out_of_scope", 0.60, Route.OUT_OF_SCOPE, "RT-OUT-OF-SCOPE"),
        ("injection", 0.50, Route.HUMAN, "RT-INJECTION"),
    ],
)
def test_at_or_above_threshold_scores(policy, score, threshold, route, rule):
    below, on, above = around(threshold)
    assert decide_route(scores(**{score: below}), facts(), policy).route is Route.AGENTS
    for value in (on, above):
        decision = decide_route(scores(**{score: value}), facts(), policy)
        assert (decision.route, decision.rule_id) == (route, rule)
        assert decision.record.stage is Stage.CLASSIFIER
        assert decision.record.inputs_summary["threshold"] == threshold


def test_out_of_scope_has_no_human_action(policy):
    decision = decide_route(scores(workflow_out_of_scope=0.9), facts(), policy)
    assert decision.human_action is HumanAction.NONE


def test_escalation_beats_clarification(policy):
    decision = decide_route(
        scores(needs_human=0.9, confidence=0.1, clear_enough=0.1), facts(), policy
    )
    assert decision.rule_id == "RT-ESCALATE"


def test_route_accepts_models(policy):
    from calvino.policy import Facts, Scores

    decision = decide_route(Scores(**scores()), Facts(**facts()), policy)
    assert decision.route is Route.AGENTS


# --- route: fail closed ------------------------------------------------------------------------


@pytest.mark.parametrize("missing", list(scores()))
def test_route_missing_score_fails_closed(policy, missing):
    partial = scores()
    del partial[missing]
    decision = decide_route(partial, facts(), policy)
    assert (decision.route, decision.rule_id) == (Route.HUMAN, "FC-SCORES")


@pytest.mark.parametrize("bad", [1.5, -0.1, float("nan"), float("inf"), "0.1", True, None])
def test_route_malformed_score_fails_closed(policy, bad):
    decision = decide_route(scores(needs_human=bad), facts(), policy)
    assert (decision.route, decision.rule_id) == (Route.HUMAN, "FC-SCORES")


def test_act_probability_is_not_accepted(policy):
    decision = decide_route(scores(act_probability=0.99), facts(), policy)
    assert decision.rule_id == "FC-SCORES"


@pytest.mark.parametrize("missing", [name for name in facts() if name != "session_ref"])
def test_route_missing_fact_fails_closed(policy, missing):
    partial = facts()
    del partial[missing]
    assert decide_route(scores(), partial, policy).rule_id == "FC-INPUTS"


@pytest.mark.parametrize(
    "override",
    [
        {"fraud_signal": "no"},
        {"fraud_signal": 0},
        {"auth_failures": -1},
        {"auth_failures": 1.5},
        {"amount": 10.0},  # amount without currency
        {"currency": "MXN"},  # currency without amount
        {"amount": float("nan"), "currency": "MXN"},
        {"amount": -5.0, "currency": "MXN"},
        {"session_ref": "raw-token-not-a-hash"},
        {"session_token": "raw-token"},  # unknown field
    ],
)
def test_route_malformed_facts_fail_closed(policy, override):
    decision = decide_route(scores(), facts(**override), policy)
    assert (decision.route, decision.rule_id) == (Route.HUMAN, "FC-INPUTS")
    assert "raw-token" not in decision.record.model_dump_json()


def test_route_unknown_currency_fails_closed(policy):
    decision = decide_route(scores(), facts(amount=10.0, currency="BRL"), policy)
    assert (decision.route, decision.rule_id) == (Route.HUMAN, "FC-CURRENCY")


def test_route_non_mapping_inputs_fail_closed(policy):
    assert decide_route(None, None, policy).rule_id == "FC-INPUTS"  # type: ignore[arg-type]


# --- gate: verdicts ----------------------------------------------------------------------------


def test_gate_allows_eligible_owned_action_under_limit(policy):
    decision = decide_gate(action(), scores(), facts(), policy)
    assert (decision.verdict, decision.rule_id) == (GateVerdict.ALLOW, "GATE-ALLOW")
    assert decision.human_action is HumanAction.NONE
    assert decision.record.stage is Stage.GATE


@pytest.mark.parametrize(
    ("name", "status"),
    [
        ("request_cancellation", "pending"),
        ("retry_payment", "declined"),
        ("open_investigation", "pending"),
        ("open_investigation", "declined"),
        ("open_investigation", "reversed"),
        ("retry_payment", "Declined"),  # dataset capitalisation
    ],
)
def test_gate_allows_each_workflow_action_on_eligible_status(policy, name, status):
    decision = decide_gate(action(name=name, transaction_status=status), scores(), facts(), policy)
    assert decision.verdict is GateVerdict.ALLOW


@pytest.mark.parametrize(
    ("name", "status"),
    [
        ("request_cancellation", "declined"),
        ("request_cancellation", "reversed"),
        ("request_cancellation", "approved"),
        ("retry_payment", "pending"),
        ("retry_payment", "reversed"),
        ("retry_payment", "approved"),
        ("open_investigation", "approved"),
        ("open_investigation", "unheard-of"),
    ],
)
def test_gate_blocks_ineligible_status(policy, name, status):
    decision = decide_gate(action(name=name, transaction_status=status), scores(), facts(), policy)
    assert (decision.verdict, decision.rule_id) == (GateVerdict.BLOCK, "GATE-INELIGIBLE")


def test_gate_blocks_when_not_owner(policy):
    decision = decide_gate(action(owner_verified=False), scores(), facts(), policy)
    assert (decision.verdict, decision.rule_id) == (GateVerdict.BLOCK, "GATE-NOT-OWNER")


@pytest.mark.parametrize(
    ("override", "rule"),
    [({"fraud_signal": True}, "HR-FRAUD"), ({"auth_failures": 3}, "HR-AUTH")],
)
def test_gate_blocks_on_fraud_and_authentication_failures(policy, override, rule):
    decision = decide_gate(action(), scores(), facts(**override), policy)
    assert (decision.verdict, decision.rule_id) == (GateVerdict.BLOCK, rule)


@pytest.mark.parametrize("override", [{"fraud_signal": True}, {"auth_failures": 9}])
def test_gate_blocking_hard_rules_win_over_amount_and_scores(policy, override):
    decision = decide_gate(action(amount=10**9), {}, facts(**override), policy)
    assert decision.verdict is GateVerdict.BLOCK


@pytest.mark.parametrize(
    ("rule", "override"),
    [case for case in HARD_CASES if case[0] in {"HR-ASKS-HUMAN", "HR-REGULATOR", "HR-VULNERABLE"}],
)
def test_gate_asks_a_person_on_remaining_hard_rules(policy, rule, override):
    decision = decide_gate(action(), scores(), facts(**override), policy)
    assert (decision.verdict, decision.rule_id) == (GateVerdict.ASK, rule)
    assert decision.human_action is HumanAction.APPROVE_ACTION


@pytest.mark.parametrize(("currency", "limit", "hard"), [("MXN", 8500, 85000), ("USD", 500, 5000)])
def test_gate_amount_limits_per_currency(policy, currency, limit, hard):
    def run(amount):
        return decide_gate(action(amount=amount, currency=currency), scores(), facts(), policy)

    assert run(limit).verdict is GateVerdict.ALLOW  # on the limit is allowed
    just_over = run(limit + 0.01)
    assert (just_over.verdict, just_over.rule_id) == (GateVerdict.ASK, "GATE-LIMIT")
    assert just_over.human_action is HumanAction.APPROVE_ACTION
    assert run(hard).rule_id == "GATE-LIMIT"
    assert run(hard + 0.01).rule_id == "HR-AMOUNT"


@pytest.mark.parametrize(
    "override",
    [{}, {"vulnerable_customer": True}, {"asks_for_human": True}, {"amount": 10**9}],
)
def test_gate_injection_blocks_even_above_the_limit_or_with_asking_rules(policy, override):
    over_limit = action(amount=override.get("amount", 9000.0))  # above the 8,500 MXN gate limit
    just_below = math.nextafter(0.50, 0)
    on = decide_gate(
        over_limit,
        scores(injection=0.50),
        facts(**{k: v for k, v in override.items() if k != "amount"}),
        policy,
    )
    assert (on.verdict, on.rule_id) == (GateVerdict.BLOCK, "GATE-INJECTION")
    below = decide_gate(
        over_limit,
        scores(injection=just_below),
        facts(**{k: v for k, v in override.items() if k != "amount"}),
        policy,
    )
    assert below.verdict is GateVerdict.ASK  # without the injection signal the person is asked


def test_gate_fraud_still_beats_injection_and_ownership_comes_first(policy):
    assert (
        decide_gate(action(), scores(injection=0.9), facts(fraud_signal=True), policy).rule_id
        == "HR-FRAUD"
    )
    blocked = decide_gate(action(owner_verified=False), scores(injection=0.9), facts(), policy)
    assert blocked.rule_id == "GATE-NOT-OWNER"


def test_gate_block_outranks_ask(policy):
    decision = decide_gate(
        action(amount=10**9, transaction_status="approved"),
        scores(),
        facts(vulnerable_customer=True),
        policy,
    )
    assert decision.rule_id == "GATE-INELIGIBLE"


@pytest.mark.parametrize(
    ("score", "threshold", "verdict", "rule"),
    [
        ("injection", 0.50, GateVerdict.BLOCK, "GATE-INJECTION"),
    ],
)
def test_gate_injection_threshold(policy, score, threshold, verdict, rule):
    below, on, above = around(threshold)
    assert (
        decide_gate(action(), scores(**{score: below}), facts(), policy).verdict
        is GateVerdict.ALLOW
    )
    for value in (on, above):
        decision = decide_gate(action(), scores(**{score: value}), facts(), policy)
        assert (decision.verdict, decision.rule_id) == (verdict, rule)


@pytest.mark.parametrize(
    ("score", "threshold", "rule"),
    [("confidence", 0.60, "GATE-LOW-CONFIDENCE"), ("clear_enough", 0.70, "GATE-UNCLEAR")],
)
def test_gate_asks_below_minimum_scores(policy, score, threshold, rule):
    below, on, above = around(threshold)
    decision = decide_gate(action(), scores(**{score: below}), facts(), policy)
    assert (decision.verdict, decision.rule_id) == (GateVerdict.ASK, rule)
    for value in (on, above):
        assert (
            decide_gate(action(), scores(**{score: value}), facts(), policy).verdict
            is GateVerdict.ALLOW
        )


def test_gate_never_reads_needs_human_or_route_scores(policy):
    decision = decide_gate(
        action(), scores(needs_human=1.0, workflow_out_of_scope=1.0), facts(), policy
    )
    assert decision.verdict is GateVerdict.ALLOW


# --- gate: fail closed -------------------------------------------------------------------------


@pytest.mark.parametrize("missing", ["clear_enough", "confidence", "injection"])
def test_gate_missing_scores_follow_the_policy(policy, missing):
    partial = scores()
    del partial[missing]
    asked = decide_gate(action(), partial, facts(), policy)
    assert (asked.verdict, asked.rule_id) == (GateVerdict.ASK, "FC-SCORES")
    strict = policy.model_copy(
        update={"gate": policy.gate.model_copy(update={"on_missing_scores": "block"})}
    )
    blocked = decide_gate(action(), partial, facts(), strict)
    assert (blocked.verdict, blocked.rule_id) == (GateVerdict.BLOCK, "FC-SCORES")


def test_gate_act_probability_fails_closed(policy):
    assert (
        decide_gate(action(), scores(act_probability=1.0), facts(), policy).rule_id == "FC-SCORES"
    )


@pytest.mark.parametrize(
    "missing", ["name", "transaction_status", "amount", "currency", "owner_verified"]
)
def test_gate_missing_action_field_blocks(policy, missing):
    partial = action()
    del partial[missing]
    decision = decide_gate(partial, scores(), facts(), policy)
    assert (decision.verdict, decision.rule_id) == (GateVerdict.BLOCK, "FC-INPUTS")


@pytest.mark.parametrize(
    "override",
    [
        {"name": "refund"},  # not a workflow action
        {"amount": -1},
        {"amount": float("inf")},
        {"owner_verified": "yes"},
        {"owner_verified": 1},
        {"transaction_status": ""},
        {"extra": 1},
    ],
)
def test_gate_malformed_action_blocks(policy, override):
    decision = decide_gate(action(**override), scores(), facts(), policy)
    assert (decision.verdict, decision.rule_id) == (GateVerdict.BLOCK, "FC-INPUTS")


def test_gate_malformed_facts_and_unknown_currency_block(policy):
    assert decide_gate(action(), scores(), {}, policy).rule_id == "FC-INPUTS"
    assert decide_gate(action(currency="BRL"), scores(), facts(), policy).rule_id == "FC-CURRENCY"


# --- records and replay ------------------------------------------------------------------------


def test_record_holds_every_input_the_route_read(policy):
    decision = decide_route(scores(), facts(amount=250.5, currency="MXN", auth_failures=1), policy)
    record = decision.record
    assert record.session_ref == REF
    assert record.policy_version == "v2"
    assert record.verdict == "agents"
    assert record.rule_id == "RT-ACT"
    assert record.scores == scores()
    assert record.inputs_summary == {
        "decision_kind": "route",
        "fact.fraud_signal": False,
        "fact.asks_for_human": False,
        "fact.auth_failures": 1,
        "fact.via_regulator": False,
        "fact.vulnerable_customer": False,
        "fact.amount": 250.5,
        "fact.currency": "MXN",
        "threshold": 0.30,
    }
    assert record.latency_ms >= 0


def test_record_holds_every_input_the_gate_read(policy):
    decision = decide_gate(action(), scores(), facts(), policy)
    summary = decision.record.inputs_summary
    assert summary["decision_kind"] == "gate"
    assert summary["action.name"] == "retry_payment"
    assert summary["action.transaction_status"] == "declined"
    assert summary["action.amount"] == 1000.0
    assert summary["action.currency"] == "MXN"
    assert summary["action.owner_verified"] is True
    assert summary["fact.fraud_signal"] is False
    assert decision.record.verdict == "allow"


def test_invalid_session_ref_is_never_logged_raw(policy):
    decision = decide_route(scores(), facts(session_ref="Bearer abc.def.ghi"), policy)
    dumped = decision.record.model_dump_json()
    assert "Bearer" not in dumped
    assert decision.record.session_ref == "0" * 64


def _cases():
    score_sets = [
        scores(),
        scores(needs_human=0.5),
        scores(needs_human=0.9),
        scores(confidence=0.1),
        scores(workflow_out_of_scope=0.8),
        scores(injection=0.9),
        scores(act_probability=0.5),
        {"needs_human": 0.1},
        {},
    ]
    fact_sets = [
        facts(),
        facts(fraud_signal=True),
        facts(vulnerable_customer=True),
        facts(amount=9999.0, currency="USD"),
        facts(amount=5.0, currency="BRL"),
        facts(session_ref="raw-token"),
        facts(auth_failures="two"),
        {},
    ]
    action_sets = [
        action(),
        action(amount=20000),
        action(owner_verified=False),
        action(transaction_status="approved"),
        action(name="refund"),
        action(currency="BRL"),
        action(amount=float("nan")),
    ]
    return score_sets, fact_sets, action_sets


def test_route_replay_reproduces_every_decision_through_the_log(policy, tmp_path):
    log = DecisionLog(tmp_path / "decisions.jsonl")
    score_sets, fact_sets, _ = _cases()
    originals = []
    for score_set, fact_set in itertools.product(score_sets, fact_sets):
        decision = decide_route(score_set, fact_set, policy)
        log.append(decision.record)
        originals.append(decision)
    for original, record in zip(originals, log, strict=True):
        again = replay_decision(record, policy)
        assert (again.route, again.rule_id) == (original.route, original.rule_id)
        assert again.record.verdict == record.verdict


def test_gate_replay_reproduces_every_decision_through_the_log(policy, tmp_path):
    log = DecisionLog(tmp_path / "decisions.jsonl")
    score_sets, fact_sets, action_sets = _cases()
    originals = []
    for score_set, fact_set, action_set in itertools.product(score_sets, fact_sets, action_sets):
        decision = decide_gate(action_set, score_set, fact_set, policy)
        log.append(decision.record)
        originals.append(decision)
    assert len(originals) > 400
    for original, record in zip(originals, log, strict=True):
        again = replay_decision(record, policy)
        assert (again.verdict, again.rule_id) == (original.verdict, original.rule_id)


def test_same_inputs_give_the_same_verdict(policy):
    runs = [decide_gate(action(), scores(), facts(), policy) for _ in range(5)]
    assert {(run.verdict, run.rule_id) for run in runs} == {(GateVerdict.ALLOW, "GATE-ALLOW")}


def test_replay_under_a_new_policy_can_change_the_verdict(policy):
    decision = decide_route(scores(needs_human=0.5), facts(), policy)
    looser = policy.model_copy(
        update={"route": policy.route.model_copy(update={"act_below": 0.6, "escalate_at": 0.9})}
    )
    assert decision.route is Route.CLARIFY
    assert replay_decision(decision.record, looser).route is Route.AGENTS


def test_replay_rejects_records_the_policy_did_not_write(policy):
    from calvino.records import DecisionRecord

    record = DecisionRecord(
        stage=Stage.VERIFIER, session_ref=REF, policy_version="v1", verdict="pass", latency_ms=1
    )
    with pytest.raises(ValueError, match="not written by the policy engine"):
        replay_decision(record, policy)
