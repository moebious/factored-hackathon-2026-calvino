"""The deterministic demo agent (TSD-010, decision 10).

Until T-301 lands the LLM agent, the language work stays templated: the
``TemplateAgent`` drafts grounded Spanish sentences from the playbook and the
verified tool results, never a field the payload lacks, so no free-form text
reaches the screen while the thesis is being judged. The plan per stage is
fixed: focus the payment (the reference in the message, else the focus the
conversation already has, else the single problem entry), fetch its detail,
then speak only from that payload. Every sentence is built to pass the
verifier's code checks: amounts and dates come from the payload verbatim,
merchant names are quoted only when the payload carries one, status words
match the verifier's vocabulary, and actions are claimed only after the
read-back the evidence confirms.
"""

from __future__ import annotations

import re
from typing import Any

from calvino.hub.agent import AgentDraft, AgentRequest, ToolCall
from calvino.hub.state import HubStage
from calvino.verifier.evidence import ToolResult

# Fixture entry references ("E-MX-002") a demo message may name.
_ENTRY_REF_RE = re.compile(r"\bE-[A-Z]{2}-\d{3}\b")

# The Spanish status words, matching the verifier's status vocabulary so a
# template can never state a status the code check would reject. Gendered
# forms: "su transferencia" is feminine, "el nuevo pago" masculine.
_STATUS_FEMININE = {
    "Pending": "pendiente",
    "Declined": "rechazada",
    "Reversed": "revertida",
    "Approved": "aprobada",
}
_STATUS_MASCULINE = {
    "Pending": "pendiente",
    "Declined": "rechazado",
    "Reversed": "revertido",
    "Approved": "aprobado",
}

# Investigation statuses in words (not payment statuses: the verifier's
# status vocabulary deliberately does not cover them).
_CASE_ES = {
    "Open": "abierto",
    "InReview": "en revisión",
    "Resolved": "resuelto",
    "Closed": "cerrado",
}

# Action keywords in demo messages. When none matches, the playbook action
# for the focused status decides (Pending -> cancellation, Declined ->
# retry); an unactionable status raises, which the hub escalates fail-closed.
_CANCEL_WORDS = ("cancel",)
_RETRY_WORDS = ("reintent", "retry", "reenvi", "volver a intentar")

# Honest templates for the paths with no data to cite; none states a fact.
NO_PROBLEMS_REPLY = "No encontré pagos con problemas en su cuenta."
PICK_REPLY = (
    "Encontré más de un pago con problemas en su cuenta. ¿Sobre cuál desea preguntar: {refs}?"
)
NO_CASE_REPLY = "No encuentro un caso abierto en su cuenta."


def _last(results: tuple[ToolResult, ...] | list[ToolResult], tool: str) -> ToolResult | None:
    """The most recent result for one tool, if the session has one."""
    return next((result for result in reversed(results) if result.tool == tool), None)


def _detail_call(entry_reference: str) -> AgentDraft:
    return AgentDraft(
        tool_calls=(
            ToolCall(tool="get_entry_detail", arguments={"entry_reference": entry_reference}),
        )
    )


def _payment_subject(payload: dict[str, Any]) -> str:
    """The grounded subject both explain and act sentences speak about.

    Built only from fields the payload carries: an optional field that is
    missing is left out, never guessed at (FR-7).
    """
    subject = f"transferencia de {payload.get('amount')} {payload.get('currency')}"
    if payload.get("remittance_information"):
        subject += f" «{payload['remittance_information']}»"
    if payload.get("booking_date"):
        subject += f" del {payload['booking_date']}"
    return subject


class TemplateAgent:
    """Drafts templated grounded replies; implements ``SupportAgent``.

    Stateless: every step is decided from the request alone (stage, message,
    the session's verified tool results and the conversation's focus), so the
    same request always drafts the same step.
    """

    def draft(self, request: AgentRequest) -> AgentDraft:
        if request.stage == HubStage.ACT.value:
            return self._act(request)
        if request.stage == HubStage.FOLLOW_UP.value:
            return self._follow_up(request)
        if self._asks_for_action(request.message):
            # Routing sends every agents turn to explain, and the Gate
            # promotes it to act when the write arrives; an explicit action
            # request therefore proposes its write from the explain step.
            # A literal keyword scan decides this, never a model (decision 10).
            return self._act(request)
        return self._explain(request)

    def _asks_for_action(self, message: str) -> bool:
        lowered = message.casefold()
        return any(word in lowered for word in _CANCEL_WORDS + _RETRY_WORDS)

    # -- explain ---------------------------------------------------------

    def _explain(self, request: AgentRequest) -> AgentDraft:
        detail = _last(request.tool_results, "get_entry_detail")
        if detail is not None:
            return AgentDraft(text=self._explain_text(detail.payload))
        if _last(request.tool_results, "list_problem_transactions") is None:
            return self._focus_call(request)
        return self._from_listing(request)

    def _explain_text(self, payload: dict[str, Any]) -> str:
        status = str(payload.get("status"))
        word = _STATUS_FEMININE.get(status, status)
        sentence = f"Su {_payment_subject(payload)} está {word}."
        if status == "Pending" and payload.get("value_date"):
            # The playbook's next step for Pending: settlement on the value
            # date, cited from the payload, never a promised time.
            sentence = (
                f"Su {_payment_subject(payload)} está {word}: "
                f"se espera la liquidación el {payload['value_date']}."
            )
        return sentence

    # -- act ---------------------------------------------------------------

    def _act(self, request: AgentRequest) -> AgentDraft:
        results = request.tool_results
        write = next(
            (r for r in reversed(results) if r.tool in ("request_cancellation", "retry_payment")),
            None,
        )
        read_back = _last(results, "get_payment_status")
        detail = _last(results, "get_entry_detail")
        if write is not None and read_back is not None:
            return AgentDraft(
                text=self._act_text(
                    write.tool, detail.payload if detail is not None else {}, read_back.payload
                )
            )
        if detail is not None:
            action = self._action_of(request, detail.payload)
            reference = detail.payload.get("entry_reference")
            return AgentDraft(
                tool_calls=(ToolCall(tool=action, arguments={"entry_reference": reference}),)
            )
        if _last(results, "list_problem_transactions") is None:
            return self._focus_call(request)
        return self._from_listing(request)

    def _act_text(self, action: str, detail: dict[str, Any], read_back: dict[str, Any]) -> str:
        # The claim words ("he cancelado", "he reintentado") appear only here,
        # and this step only runs once the read-back result is in evidence.
        if action == "request_cancellation":
            return f"He cancelado su {_payment_subject(detail)}."
        status = str(read_back.get("status"))
        word = _STATUS_MASCULINE.get(status, status)
        return f"He reintentado su {_payment_subject(detail)}; el nuevo pago está {word}."

    def _action_of(self, request: AgentRequest, detail: dict[str, Any]) -> str:
        lowered = request.message.casefold()
        if any(word in lowered for word in _CANCEL_WORDS):
            return "request_cancellation"
        if any(word in lowered for word in _RETRY_WORDS):
            return "retry_payment"
        status = detail.get("status")
        if status == "Pending":
            return "request_cancellation"
        if status == "Declined":
            return "retry_payment"
        raise RuntimeError(f"the template agent has no act plan for status {status!r}")

    # -- follow up -----------------------------------------------------------

    def _follow_up(self, request: AgentRequest) -> AgentDraft:
        result = _last(request.tool_results, "get_investigation_status")
        if result is None:
            if not request.case_ref:
                return AgentDraft(text=NO_CASE_REPLY)
            return AgentDraft(
                tool_calls=(
                    ToolCall(
                        tool="get_investigation_status",
                        arguments={"case_id": request.case_ref},
                    ),
                )
            )
        payload = result.payload
        case_id = payload.get("case_id") or request.case_ref or ""
        status = str(payload.get("status"))
        word = _CASE_ES.get(status, status)
        return AgentDraft(text=f"Su caso {case_id} está {word}.")

    # -- focus ----------------------------------------------------------------

    def _focus_call(self, request: AgentRequest) -> AgentDraft:
        """The next step toward focusing a payment.

        The reference in the message wins; then the focus the conversation
        already has; otherwise the problem-transactions list, which the next
        step narrows to the single problem entry.
        """
        match = _ENTRY_REF_RE.search(request.message)
        if match:
            return _detail_call(match.group())
        if request.entry_reference:
            return _detail_call(request.entry_reference)
        return AgentDraft(tool_calls=(ToolCall(tool="list_problem_transactions"),))

    def _from_listing(self, request: AgentRequest) -> AgentDraft:
        """With the list in hand: the single problem entry's detail, or an
        honest template. Never picks between several payments on its own:
        choosing the payment is the customer's (or the clarify stage's)."""
        listing = _last(request.tool_results, "list_problem_transactions")
        entries = (listing.payload.get("entries") if listing is not None else None) or []
        if len(entries) == 1 and isinstance(entries[0].get("entry_reference"), str):
            return _detail_call(entries[0]["entry_reference"])
        if not entries:
            return AgentDraft(text=NO_PROBLEMS_REPLY)
        refs = ", ".join(sorted(str(entry.get("entry_reference")) for entry in entries))
        return AgentDraft(text=PICK_REPLY.format(refs=refs))
