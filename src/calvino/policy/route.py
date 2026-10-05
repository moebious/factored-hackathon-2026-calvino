"""``decide_route``: where the hub sends a request (agents, clarify, human or out of scope).

Order of evaluation: input checks (fail closed), the hard rules (first match wins, before any
score is read), then the thresholds on calibrated probabilities. Ties go to the safer side.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from calvino.policy._common import as_mapping, make_record, parse, triggered_hard_rules
from calvino.policy.config import Policy, RoutePolicy
from calvino.policy.inputs import ROUTE_SCORES, Facts, Scores
from calvino.records import DecisionRecord, HumanAction, Route, Stage


def required_route_scores(rules: RoutePolicy) -> tuple[str, ...]:
    """The scores this policy reads: a missing one fails closed to a person (FC-SCORES).

    v1 and v2 read the original six. A policy that switches a gate off no longer requires its
    score, and one that adds a gate requires the score it reads.
    """
    required = [
        name
        for name in ROUTE_SCORES
        if not (name == "needs_human" and not rules.use_needs_human)
        and not (name == "clear_enough" and rules.min_clear_enough is None)
    ]
    if rules.talk_to_person_at is not None:
        required.append("talk_to_person")
    if rules.min_stuck_payment is not None:
        required.append("workflow_stuck_payment")
    return tuple(required)


@dataclass(frozen=True)
class RouteDecision:
    """The route, how a person is involved, the rule that decided and its log record."""

    route: Route
    human_action: HumanAction
    rule_id: str
    record: DecisionRecord


def decide_route(
    scores: Scores | dict[str, object],
    facts: Facts | dict[str, object],
    policy: Policy,
) -> RouteDecision:
    """Decide the route for one request. Pure: the same inputs and policy give the same verdict."""
    started = perf_counter()
    raw_facts, raw_scores = as_mapping(facts), as_mapping(scores)

    def done(
        route: Route,
        rule_id: str,
        stage: Stage,
        threshold: float | None = None,
        errors: list[str] | None = None,
    ) -> RouteDecision:
        human = HumanAction.FULL_TRANSFER if route is Route.HUMAN else HumanAction.NONE
        record = make_record(
            kind="route",
            stage=stage,
            policy=policy,
            verdict=route.value,
            rule_id=rule_id,
            latency_ms=(perf_counter() - started) * 1000,
            raw_facts=raw_facts,
            raw_action=None,
            raw_scores=raw_scores,
            threshold=threshold,
            input_errors=errors,
        )
        return RouteDecision(route, human, rule_id, record)

    parsed_facts, fact_errors = parse(Facts, raw_facts)
    if parsed_facts is None:
        return done(Route.HUMAN, "FC-INPUTS", Stage.HARD_RULES, errors=fact_errors)
    limits = policy.hard_rules.amount_limit
    if parsed_facts.currency is not None and parsed_facts.currency not in limits:
        return done(Route.HUMAN, "FC-CURRENCY", Stage.HARD_RULES)

    fired = triggered_hard_rules(parsed_facts, parsed_facts.amount, parsed_facts.currency, policy)
    if fired:
        return done(Route.HUMAN, fired[0], Stage.HARD_RULES)

    parsed, score_errors = parse(Scores, raw_scores)
    rules = policy.route
    if parsed is None or any(
        getattr(parsed, name) is None for name in required_route_scores(rules)
    ):
        return done(Route.HUMAN, "FC-SCORES", Stage.CLASSIFIER, errors=score_errors)

    if parsed.workflow_dispute_or_fraud >= rules.dispute_or_fraud_at:  # type: ignore[operator]
        return done(Route.HUMAN, "RT-DISPUTE-FRAUD", Stage.CLASSIFIER, rules.dispute_or_fraud_at)
    if parsed_facts.entry_reference is not None and not _requests_a_person(parsed, rules):
        # A cited entry reference anchors the turn on it: the message names
        # a concrete bank entry, so it is explained from a verified read
        # instead of being judged out of scope by phrasing. Fraud and hard
        # rules already won above, injection and requests for a person still
        # win through the guard, and the agent path still verifies while the
        # Gate still guards every write.
        return done(Route.AGENTS, "RT-REF-ANCHORED", Stage.CLASSIFIER)
    if parsed.workflow_out_of_scope >= rules.out_of_scope_at:  # type: ignore[operator]
        return done(Route.OUT_OF_SCOPE, "RT-OUT-OF-SCOPE", Stage.CLASSIFIER, rules.out_of_scope_at)
    if parsed.injection >= rules.injection_at:  # type: ignore[operator]
        return done(Route.HUMAN, "RT-INJECTION", Stage.CLASSIFIER, rules.injection_at)
    if rules.talk_to_person_at is not None and parsed.talk_to_person >= rules.talk_to_person_at:  # type: ignore[operator]
        return done(Route.HUMAN, "RT-TALK-TO-PERSON", Stage.CLASSIFIER, rules.talk_to_person_at)
    needs_human = parsed.needs_human if rules.use_needs_human else None
    if needs_human is not None and needs_human >= rules.escalate_at:
        return done(Route.HUMAN, "RT-ESCALATE", Stage.CLASSIFIER, rules.escalate_at)
    if (
        rules.min_stuck_payment is not None
        and parsed.workflow_stuck_payment < rules.min_stuck_payment
    ):  # type: ignore[operator]
        return done(
            Route.CLARIFY, "RT-CLARIFY-NOT-STUCK", Stage.CLASSIFIER, rules.min_stuck_payment
        )
    if parsed.confidence < rules.min_confidence:  # type: ignore[operator]
        return done(Route.CLARIFY, "RT-CLARIFY-CONFIDENCE", Stage.CLASSIFIER, rules.min_confidence)
    if rules.min_clear_enough is not None and parsed.clear_enough < rules.min_clear_enough:  # type: ignore[operator]
        return done(Route.CLARIFY, "RT-CLARIFY-UNCLEAR", Stage.CLASSIFIER, rules.min_clear_enough)
    if needs_human is not None and needs_human >= rules.act_below:
        return done(Route.CLARIFY, "RT-CLARIFY-BAND", Stage.CLASSIFIER, rules.act_below)
    return done(Route.AGENTS, "RT-ACT", Stage.CLASSIFIER, rules.act_below)


def _requests_a_person(parsed: Scores, rules: RoutePolicy) -> bool:
    """Whether a human verdict below the reference anchor would fire.

    Mirrors the injection, talk-to-person and escalate gates with the same
    thresholds, so the anchor never overrides them: a manipulated request is
    never explained, and an explicit or scored request for a person still
    goes to a person. Reads the same ``rules`` object, so it cannot drift.
    """
    needs_human = parsed.needs_human if rules.use_needs_human else None
    return (
        parsed.injection >= rules.injection_at  # type: ignore[operator]
        or (
            rules.talk_to_person_at is not None and parsed.talk_to_person >= rules.talk_to_person_at  # type: ignore[operator]
        )
        or (needs_human is not None and needs_human >= rules.escalate_at)  # type: ignore[operator]
    )
