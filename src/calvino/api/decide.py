"""One demo decision: Laya probabilities -> policy verdict -> decision log (TSD-003).

The demo endpoint runs the whole System 1 chain on a short text: the workflow
question set (TSD-005), the score mapping ``decide_route`` reads (TSD-001) and
an append to ``decisions.jsonl``, so every demo decision is auditable. The
payload returned to the frontend is the glass box (decision 10): the verdict,
the rule that fired, the calibrated scores and the per-question probabilities.
"""

from __future__ import annotations

from pydantic import BaseModel

from calvino.api.loader import SystemOneLoader
from calvino.classifiers import LayaAnswer, workflow_questions
from calvino.classifiers.laya import (
    QUESTION_CLEAR_ENOUGH,
    QUESTION_INJECTION,
    QUESTION_INTENT,
    QUESTION_NEEDS_HUMAN,
    QUESTION_WORKFLOW_AREA,
)
from calvino.decision_log import DecisionLog
from calvino.policy import Facts, Policy, decide_route
from calvino.records import HumanAction, Route, session_ref_for

# The demo has no real customer session. This fixed token is hashed with
# session_ref_for into the record's session_ref, so the log schema is
# satisfied and no token-like value ever reaches the log.
DEMO_SESSION_TOKEN = "calvino-demo"


class DemoAnswer(BaseModel):
    """One question's glass-box detail: what was chosen, with what confidence."""

    chosen_option: str
    confidence: float
    probabilities: dict[str, float]


class DemoDecision(BaseModel):
    """The demo decision payload: verdict, rule fired, scores and probabilities."""

    decision_id: str
    route: Route
    human_action: HumanAction
    rule_id: str
    policy_version: str
    scores: dict[str, float]
    answers: dict[str, DemoAnswer]


def scores_from_answers(
    answers: dict[str, LayaAnswer], confidence_source: str = "min_all"
) -> dict[str, float]:
    """Map Laya's workflow answers onto the score fields ``decide_route`` reads.

    Each score is one specific option's probability, except
    ``workflow_dispute_or_fraud`` (the sum of two workflow-area options) and
    ``confidence``: the minimum calibrated confidence across the answers, the
    most conservative aggregate until the hub defines the real one (T-204).
    ``confidence_source`` is the policy's choice (``route.confidence_source``): ``min_all`` is
    the original aggregate, ``workflow_area`` uses the calibrated confidence of the workflow-area
    answer alone, because the minimum over all five answers is dragged down by the six-option
    intent question and blocked routine messages by itself (TSD-021).
    A missing question or option means the question set drifted from the
    policy, so this raises instead of guessing a score.
    """
    try:
        area = answers[QUESTION_WORKFLOW_AREA].probabilities
        return {
            "needs_human": answers[QUESTION_NEEDS_HUMAN].probabilities["human needed"],
            "clear_enough": answers[QUESTION_CLEAR_ENOUGH].probabilities["clear"],
            "injection": answers[QUESTION_INJECTION].probabilities["risky"],
            "workflow_out_of_scope": area["out of scope"],
            "workflow_stuck_payment": area["stuck payment"],
            "talk_to_person": answers[QUESTION_INTENT].probabilities["talk to a person"],
            "workflow_dispute_or_fraud": (
                area["dispute or unrecognised charge"] + area["fraud or stolen access"]
            ),
            "confidence": (
                answers[QUESTION_WORKFLOW_AREA].confidence
                if confidence_source == "workflow_area"
                else min(answer.confidence for answer in answers.values())
            ),
        }
    except KeyError as error:
        raise ValueError(f"incomplete laya answers: missing {error}") from error


def run_demo_decision(
    text: str,
    loader: SystemOneLoader,
    policy: Policy,
    log: DecisionLog,
) -> DemoDecision:
    """Run one full System 1 decision, log it and return the glass-box payload.

    The session facts are inert on purpose: ``Facts`` carries what the harness
    knows, none of it from a model, and the demo has no session, amounts or
    authentication history. Hard rules therefore cannot fire here; the verdict
    comes from the classifier thresholds, and ``decide_route`` itself fails
    closed to a human when a score is missing.
    """
    answers_list = loader.classify(text, workflow_questions())
    answers = {answer.question_id: answer for answer in answers_list}
    scores = scores_from_answers(answers, policy.route.confidence_source)
    facts = Facts(
        session_ref=session_ref_for(DEMO_SESSION_TOKEN),
        fraud_signal=False,
        asks_for_human=False,
        auth_failures=0,
        via_regulator=False,
        vulnerable_customer=False,
    )
    decision = decide_route(scores, facts, policy)
    log.append(decision.record)
    return DemoDecision(
        decision_id=decision.record.decision_id,
        route=decision.route,
        human_action=decision.human_action,
        rule_id=decision.rule_id,
        policy_version=policy.version,
        scores=scores,
        answers={
            question_id: DemoAnswer(
                chosen_option=answer.chosen_option,
                confidence=answer.confidence,
                probabilities=answer.probabilities,
            )
            for question_id, answer in answers.items()
        },
    )
