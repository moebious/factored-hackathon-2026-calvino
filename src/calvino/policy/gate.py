"""``decide_gate``: allow, ask a person or block, before a consequential tool call.

Order of evaluation (the first match decides): input checks (block), blocking hard rules (fraud,
repeated authentication failures), ownership and eligibility (block), the injection score when
present (block), the hard rules and limits that need a person (ask), then the remaining Laya
scores. Block always outranks ask, so an ineligible or manipulated action is never put in front
of an approver. Missing scores fail closed per ``gate.on_missing_scores``.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from calvino.policy._common import as_mapping, make_record, parse, triggered_hard_rules
from calvino.policy.config import Policy
from calvino.policy.inputs import GATE_SCORES, Facts, GateAction, Scores
from calvino.records import DecisionRecord, GateVerdict, HumanAction, Stage


@dataclass(frozen=True)
class GateDecision:
    """The verdict, how a person is involved (``approve_action`` when asking), the rule that
    decided and its log record."""

    verdict: GateVerdict
    human_action: HumanAction
    rule_id: str
    record: DecisionRecord


def decide_gate(
    action: GateAction | dict[str, object],
    scores: Scores | dict[str, object],
    facts: Facts | dict[str, object],
    policy: Policy,
) -> GateDecision:
    """Decide whether the action may run. Pure: the same inputs and policy give the same verdict."""
    started = perf_counter()
    raw_action, raw_scores, raw_facts = as_mapping(action), as_mapping(scores), as_mapping(facts)

    def done(
        verdict: GateVerdict,
        rule_id: str,
        threshold: float | None = None,
        errors: list[str] | None = None,
    ) -> GateDecision:
        human = HumanAction.APPROVE_ACTION if verdict is GateVerdict.ASK else HumanAction.NONE
        record = make_record(
            kind="gate",
            stage=Stage.GATE,
            policy=policy,
            verdict=verdict.value,
            rule_id=rule_id,
            latency_ms=(perf_counter() - started) * 1000,
            raw_facts=raw_facts,
            raw_action=raw_action,
            raw_scores=raw_scores,
            threshold=threshold,
            input_errors=errors,
        )
        return GateDecision(verdict, human, rule_id, record)

    parsed_facts, fact_errors = parse(Facts, raw_facts)
    parsed_action, action_errors = parse(GateAction, raw_action)
    if parsed_facts is None or parsed_action is None:
        return done(GateVerdict.BLOCK, "FC-INPUTS", errors=fact_errors + action_errors)
    if parsed_action.currency not in policy.hard_rules.amount_limit:
        return done(GateVerdict.BLOCK, "FC-CURRENCY")

    fired = triggered_hard_rules(parsed_facts, parsed_action.amount, parsed_action.currency, policy)
    for rule in ("HR-FRAUD", "HR-AUTH"):
        if rule in fired:
            return done(GateVerdict.BLOCK, rule)
    if not parsed_action.owner_verified:
        return done(GateVerdict.BLOCK, "GATE-NOT-OWNER")
    eligible = policy.gate.eligible_statuses.get(parsed_action.name.value, [])
    if parsed_action.transaction_status.lower() not in eligible:
        return done(GateVerdict.BLOCK, "GATE-INELIGIBLE")
    parsed, score_errors = parse(Scores, raw_scores)
    if parsed is not None and parsed.injection is not None:
        if parsed.injection >= policy.gate.injection_at:
            return done(GateVerdict.BLOCK, "GATE-INJECTION", policy.gate.injection_at)
    if fired:  # only HR-AMOUNT, HR-ASKS-HUMAN, HR-REGULATOR, HR-VULNERABLE remain
        return done(GateVerdict.ASK, fired[0])
    if parsed_action.amount > policy.gate.allow_amount_limit[parsed_action.currency]:
        return done(GateVerdict.ASK, "GATE-LIMIT")

    if parsed is None or any(getattr(parsed, name) is None for name in GATE_SCORES):
        fallback = GateVerdict(policy.gate.on_missing_scores)
        return done(fallback, "FC-SCORES", errors=score_errors)

    gate = policy.gate
    if parsed.confidence < gate.min_confidence:  # type: ignore[operator]
        return done(GateVerdict.ASK, "GATE-LOW-CONFIDENCE", gate.min_confidence)
    if parsed.clear_enough < gate.min_clear_enough:  # type: ignore[operator]
        return done(GateVerdict.ASK, "GATE-UNCLEAR", gate.min_clear_enough)
    return done(GateVerdict.ALLOW, "GATE-ALLOW")
