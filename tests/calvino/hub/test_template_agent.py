"""Unit tests for the TemplateAgent (TSD-010): no model calls, no graph.

Every draft is decided from the request alone, so the tests build requests
with fabricated tool results and assert the fixed plan: focus the payment,
fetch its detail, then speak only from the payload. The grounded sentences
are checked against the verifier's own code checks — the templates must
pass the same cascade every other draft passes.
"""

from __future__ import annotations

import pytest

from calvino.hub import AgentRequest, HubStage, TemplateAgent
from calvino.verifier.code_checks import (
    check_amounts_dates_merchants,
    check_claimed_actions_read_back,
    check_no_other_customer_data,
    check_reply_language,
    check_stated_status,
)
from calvino.verifier.evidence import ToolResult, evidence_from_tool_results
from calvino.verifier.verdicts import CriterionVerdict

# The E-MX-002 detail as the graph serializes it (Pending, with merchant).
DETAIL_MX = ToolResult(
    tool="get_entry_detail",
    payload={
        "entry_reference": "E-MX-002",
        "amount": "5000.00",
        "currency": "MXN",
        "status": "Pending",
        "booking_date": "2026-06-10",
        "value_date": "2026-06-11",
        "remittance_information": "Transfer to a friend",
    },
)
# The E-US-001 detail (Declined) and its retry read-back (new payment Pending).
DETAIL_US = ToolResult(
    tool="get_entry_detail",
    payload={
        "entry_reference": "E-US-001",
        "amount": "120.00",
        "currency": "USD",
        "status": "Declined",
        "booking_date": "2026-06-15",
        "value_date": "2026-06-15",
        "remittance_information": "Tuition",
    },
)
RETRY_READ_BACK = ToolResult(
    tool="get_payment_status",
    payload={"original_reference": "E-US-001", "status": "Pending"},
)


def request(stage: HubStage, message: str = "", **kwargs) -> AgentRequest:
    return AgentRequest(stage=stage.value, message=message, **kwargs)


def code_verdicts(
    text: str, results: list[ToolResult], **evidence_kwargs
) -> list[CriterionVerdict]:
    """Run the five code checks over a draft, exactly as the cascade does."""
    evidence = evidence_from_tool_results(results, **evidence_kwargs)
    return [
        check(text, evidence)
        for check in (
            check_amounts_dates_merchants,
            check_stated_status,
            check_claimed_actions_read_back,
            check_no_other_customer_data,
            check_reply_language,
        )
    ]


def assert_grounded(text: str, results: list[ToolResult], **evidence_kwargs) -> None:
    failed = [
        verdict for verdict in code_verdicts(text, results, **evidence_kwargs) if not verdict.passed
    ]
    assert not failed, [verdict.reason for verdict in failed]


def test_explain_focuses_the_reference_in_the_message():
    draft = TemplateAgent().draft(request(HubStage.EXPLAIN, "¿Por qué sigue pendiente E-MX-002?"))
    assert [(call.tool, call.arguments) for call in draft.tool_calls] == [
        ("get_entry_detail", {"entry_reference": "E-MX-002"})
    ]


def test_explain_uses_the_conversation_focus():
    draft = TemplateAgent().draft(
        request(HubStage.EXPLAIN, "¿Por qué sigue pendiente?", entry_reference="E-MX-002")
    )
    assert draft.tool_calls[0].arguments == {"entry_reference": "E-MX-002"}


def test_explain_lists_problem_payments_without_a_focus():
    draft = TemplateAgent().draft(request(HubStage.EXPLAIN, "¿Por qué sigue pendiente mi pago?"))
    assert [call.tool for call in draft.tool_calls] == ["list_problem_transactions"]


def test_explain_details_the_single_problem_entry():
    listing = ToolResult(
        tool="list_problem_transactions",
        payload={"entries": [DETAIL_US.payload]},
    )
    draft = TemplateAgent().draft(
        request(HubStage.EXPLAIN, "¿Qué pasó con mi pago?", tool_results=[listing])
    )
    assert draft.tool_calls[0].arguments == {"entry_reference": "E-US-001"}


def test_explain_never_picks_between_several_payments():
    listing = ToolResult(
        tool="list_problem_transactions",
        payload={"entries": [DETAIL_MX.payload, DETAIL_US.payload]},
    )
    draft = TemplateAgent().draft(
        request(HubStage.EXPLAIN, "¿Qué pasó con mi pago?", tool_results=[listing])
    )
    assert draft.text is not None and not draft.tool_calls
    assert "E-MX-002" in draft.text and "E-US-001" in draft.text
    # The question cites references only: no amount, date or status claim.
    assert_grounded(draft.text, [listing])


def test_cancel_keyword_in_explain_proposes_the_write():
    """An explicit cancellation proposes its write from the explain step.

    Routing sends every agents turn to explain; the Gate promotes the turn
    to act when the write arrives, so the keyword scan (never a model) is
    what starts the act plan.
    """
    draft = TemplateAgent().draft(
        request(HubStage.EXPLAIN, "Cancela mi transferencia", tool_results=[DETAIL_MX])
    )
    assert [(call.tool, call.arguments) for call in draft.tool_calls] == [
        ("request_cancellation", {"entry_reference": "E-MX-002"})
    ]


def test_retry_keyword_in_explain_proposes_the_write():
    draft = TemplateAgent().draft(
        request(HubStage.EXPLAIN, "¿Pueden reintentar mi pago?", tool_results=[DETAIL_US])
    )
    assert [(call.tool, call.arguments) for call in draft.tool_calls] == [
        ("retry_payment", {"entry_reference": "E-US-001"})
    ]


def test_explain_without_problem_payments_is_honest():
    listing = ToolResult(tool="list_problem_transactions", payload={"entries": []})
    draft = TemplateAgent().draft(
        request(HubStage.EXPLAIN, "¿Qué pasó con mi pago?", tool_results=[listing])
    )
    assert draft.text == "No encontré pagos con problemas en su cuenta."
    assert_grounded(draft.text, [listing])


def test_explain_speaks_only_from_the_detail_payload():
    draft = TemplateAgent().draft(
        request(HubStage.EXPLAIN, "¿Por qué sigue pendiente?", tool_results=[DETAIL_MX])
    )
    assert draft.text == (
        "Su transferencia de 5000.00 MXN «Transfer to a friend» del 2026-06-10 "
        "está pendiente: se espera la liquidación el 2026-06-11."
    )
    assert_grounded(draft.text, [DETAIL_MX])


def test_explain_leaves_out_a_merchant_the_payload_lacks():
    without_merchant = ToolResult(
        tool="get_entry_detail",
        payload={k: v for k, v in DETAIL_MX.payload.items() if k != "remittance_information"},
    )
    draft = TemplateAgent().draft(
        request(HubStage.EXPLAIN, "¿Por qué sigue pendiente?", tool_results=[without_merchant])
    )
    assert "«" not in (draft.text or "")
    assert_grounded(draft.text or "", [without_merchant])


def test_act_plans_the_playbook_action_for_the_focused_status():
    agent = TemplateAgent()
    # No keyword in the message: the focused status decides (playbook v1).
    pending = agent.draft(
        request(HubStage.ACT, "¿Pueden resolver mi pago?", tool_results=[DETAIL_MX])
    )
    assert [(call.tool, call.arguments) for call in pending.tool_calls] == [
        ("request_cancellation", {"entry_reference": "E-MX-002"})
    ]
    declined = agent.draft(
        request(HubStage.ACT, "¿Pueden resolver mi pago?", tool_results=[DETAIL_US])
    )
    assert declined.tool_calls[0].tool == "retry_payment"


def test_act_honours_the_action_keyword_in_the_message():
    draft = TemplateAgent().draft(
        request(HubStage.ACT, "Quiero cancelar mi transferencia", tool_results=[DETAIL_MX])
    )
    assert draft.tool_calls[0].tool == "request_cancellation"
    draft = TemplateAgent().draft(
        request(HubStage.ACT, "¿Pueden reintentar mi pago?", tool_results=[DETAIL_US])
    )
    assert draft.tool_calls[0].tool == "retry_payment"


def test_act_focuses_like_explain_before_the_write():
    draft = TemplateAgent().draft(request(HubStage.ACT, "Quiero cancelar mi transferencia"))
    assert [call.tool for call in draft.tool_calls] == ["list_problem_transactions"]


def test_act_claims_the_action_only_after_the_read_back():
    results = [
        DETAIL_MX,
        ToolResult(
            tool="request_cancellation",
            payload={"original_reference": "E-MX-002", "outcome": "Accepted"},
        ),
        ToolResult(
            tool="get_payment_status",
            payload={"original_reference": "E-MX-002", "status": "Approved"},
        ),
    ]
    draft = TemplateAgent().draft(request(HubStage.ACT, "Quiero cancelar", tool_results=results))
    assert draft.text == (
        "He cancelado su transferencia de 5000.00 MXN «Transfer to a friend» del 2026-06-10."
    )
    # The claim passes the read-back check with the evidence the act node built.
    assert_grounded(draft.text, results, read_backs={"cancel_transfer"})


def test_act_reports_the_retried_payment_from_the_read_back():
    results = [
        DETAIL_US,
        ToolResult(tool="retry_payment", payload={"original_reference": "E-US-001"}),
        RETRY_READ_BACK,
    ]
    draft = TemplateAgent().draft(
        request(HubStage.ACT, "¿Pueden reintentar?", tool_results=results)
    )
    assert draft.text == (
        "He reintentado su transferencia de 120.00 USD «Tuition» del 2026-06-15; "
        "el nuevo pago está pendiente."
    )
    assert_grounded(draft.text, results, read_backs={"retry_payment"})


def test_act_without_an_actionable_status_fails_closed():
    reversed_entry = ToolResult(
        tool="get_entry_detail",
        payload={**DETAIL_MX.payload, "status": "Reversed"},
    )
    with pytest.raises(RuntimeError):
        TemplateAgent().draft(
            request(HubStage.ACT, "¿Pueden resolver mi pago?", tool_results=[reversed_entry])
        )


def test_follow_up_reads_the_case_before_answering():
    draft = TemplateAgent().draft(
        request(HubStage.FOLLOW_UP, "¿Cómo va mi caso?", case_ref="CASE-1")
    )
    assert [(call.tool, call.arguments) for call in draft.tool_calls] == [
        ("get_investigation_status", {"case_id": "CASE-1"})
    ]


def test_follow_up_without_a_case_is_honest():
    draft = TemplateAgent().draft(request(HubStage.FOLLOW_UP, "¿Cómo va mi caso?"))
    assert draft.text == "No encuentro un caso abierto en su cuenta."
    assert not draft.tool_calls


def test_follow_up_states_the_case_status_from_the_payload():
    result = ToolResult(
        tool="get_investigation_status",
        payload={"case_id": "CASE-1", "status": "InReview", "next_step": "We will call you"},
    )
    draft = TemplateAgent().draft(
        request(HubStage.FOLLOW_UP, "¿Cómo va mi caso?", case_ref="CASE-1", tool_results=[result])
    )
    assert draft.text == "Su caso CASE-1 está en revisión."
    assert_grounded(draft.text, [result])
