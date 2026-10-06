"""Governed ISO 20022 XML Message Builder and Parser (TSD-034, T-604).

Implements deterministic bank-facing ISO 20022 messaging for stuck payment operations:
- Outbound: camt.056.001.08 (FIToFIPaymentCancellationRequest)
- Inbound:  camt.029.001.09 (ResolutionOfInvestigation)

Strict boundaries (decision 36):
- Zero LLM generation of XML or status codes.
- Deterministic schema-aware builder and parser.
- Fail-closed validation: references, amounts, currencies, and IDs must match exactly.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from decimal import Decimal

from calvino.tools.contracts import CancellationOutcome, CancellationResponse
from calvino.tools.errors import Rule, ToolRefusal

# Standard ISO 20022 XML namespaces
CAMT_056_NS = "urn:iso:std:iso:20022:tech:xsd:camt.056.001.08"
CAMT_029_NS = "urn:iso:std:iso:20022:tech:xsd:camt.029.001.09"


def _clean_text(elem: ET.Element | None) -> str:
    if elem is None or elem.text is None:
        return ""
    return elem.text.strip()


def _find_elem(parent: ET.Element | None, tag: str) -> ET.Element | None:
    """Find child element matching tag with or without namespace."""
    if parent is None:
        return None
    for child in parent:
        local_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if local_tag == tag:
            return child
    return None


def _find_text(parent: ET.Element | None, tag: str) -> str:
    elem = _find_elem(parent, tag)
    return _clean_text(elem)


class Iso20022CancellationClient:
    """Builds outbound camt.056 XML and parses/validates inbound camt.029 XML."""

    @staticmethod
    def build_cancellation_request_xml(
        *,
        entry_reference: str,
        amount: Decimal,
        currency: str,
        customer_id: str,
        idempotency_key: str,
        reason: str = "Customer request",
        created_at: datetime | None = None,
    ) -> str:
        """Construct a deterministic camt.056.001.08 XML cancellation request."""
        now = created_at or datetime.now(UTC)
        cre_dt_tm = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        msg_id = f"CALVINO-CXL-{idempotency_key}"

        doc = ET.Element("Document", xmlns=CAMT_056_NS)
        req = ET.SubElement(doc, "FIToFIPmtCxlReq")

        # Group Header
        grp_hdr = ET.SubElement(req, "GrpHdr")
        ET.SubElement(grp_hdr, "MsgId").text = msg_id
        ET.SubElement(grp_hdr, "CreDtTm").text = cre_dt_tm

        # Assignor / Customer context
        assgnr = ET.SubElement(req, "Assgnr")
        pty = ET.SubElement(assgnr, "Pty")
        pty_id = ET.SubElement(pty, "Id")
        org_id = ET.SubElement(pty_id, "OrgId")
        othr = ET.SubElement(org_id, "Othr")
        ET.SubElement(othr, "Id").text = customer_id

        # Underlying Transaction Details
        undrlyg = ET.SubElement(req, "Undrlyg")
        tx_inf = ET.SubElement(undrlyg, "TxInf")
        ET.SubElement(tx_inf, "CxlId").text = f"CXL-{idempotency_key}"
        ET.SubElement(tx_inf, "OrgnlTxId").text = entry_reference

        # Original transaction amount
        orgnl_tx_ref = ET.SubElement(tx_inf, "OrgnlTxRef")
        amt_elem = ET.SubElement(orgnl_tx_ref, "Amt")
        instd_amt = ET.SubElement(amt_elem, "InstdAmt", Ccy=currency)
        instd_amt.text = f"{amount:.2f}"

        # Cancellation Reason
        cxl_rsn_inf = ET.SubElement(tx_inf, "CxlRsnInf")
        rsn = ET.SubElement(cxl_rsn_inf, "Rsn")
        ET.SubElement(rsn, "Prtry").text = reason

        return ET.tostring(doc, encoding="utf-8", xml_declaration=True).decode("utf-8")

    @staticmethod
    def parse_and_verify_cancellation_response(
        response_xml: str,
        *,
        expected_reference: str,
        expected_idempotency_key: str,
    ) -> CancellationResponse:
        """Parse camt.029 XML response, verify reference read-back, and return result."""
        if not response_xml or not response_xml.strip():
            raise ToolRefusal(
                Rule.SOURCE_INCOMPLETE,
                "empty XML response received from core middleware",
            )

        try:
            root = ET.fromstring(response_xml)
        except ET.ParseError as e:
            raise ToolRefusal(
                Rule.SOURCE_INCOMPLETE,
                f"malformed ISO 20022 XML received from core middleware: {e}",
            ) from e

        rsltn = _find_elem(root, "RsltnOfInvstgtn")
        if rsltn is None:
            raise ToolRefusal(
                Rule.SOURCE_INCOMPLETE,
                "missing RsltnOfInvstgtn in ISO 20022 camt.029 message",
            )

        # 1. Verify Resolved Case ID matches expected cancellation ID
        rslvd_case = _find_elem(rsltn, "RslvdCase")
        expected_cxl_id = f"CXL-{expected_idempotency_key}"
        case_id = _find_text(rslvd_case, "Id")
        if case_id != expected_cxl_id:
            msg = (
                f"ISO 20022 correlation error: expected case ID "
                f"'{expected_cxl_id}', got '{case_id}'"
            )
            raise ToolRefusal(Rule.SOURCE_INCOMPLETE, msg)

        # 2. Extract Cancellation Status Details
        cxl_dtls = _find_elem(rsltn, "CxlDtls")
        if cxl_dtls is None:
            raise ToolRefusal(
                Rule.SOURCE_INCOMPLETE,
                "missing CxlDtls in ISO 20022 camt.029 response",
            )

        tx_inf = _find_elem(cxl_dtls, "TxInfAndSts")
        if tx_inf is None:
            raise ToolRefusal(
                Rule.SOURCE_INCOMPLETE,
                "missing TxInfAndSts in ISO 20022 response",
            )

        # 3. Verify Original Transaction ID Read-Back
        undrlyg = _find_elem(tx_inf, "Undrlyg")
        resp_ref = ""
        if undrlyg is not None:
            tx = _find_elem(undrlyg, "TxInf")
            if tx is not None:
                resp_ref = _find_text(tx, "OrgnlTxId")

        if resp_ref != expected_reference:
            msg = (
                f"ISO 20022 reference mismatch: expected read-back "
                f"'{expected_reference}', got '{resp_ref}'"
            )
            raise ToolRefusal(Rule.SOURCE_INCOMPLETE, msg)

        # 4. Extract Status Code & Reason
        status_code = _find_text(tx_inf, "CxlStsId")
        rsn_inf = _find_elem(tx_inf, "CxlStsRsnInf")
        rejection_reason = None
        if rsn_inf is not None:
            rsn = _find_elem(rsn_inf, "Rsn")
            if rsn is not None:
                rejection_reason = _find_text(rsn, "Cd") or None

        if status_code in ("CNCL", "ACCP"):
            outcome = CancellationOutcome.ACCEPTED
            message = "Payment cancellation accepted by core banking middleware."
        elif status_code == "RJCT":
            outcome = CancellationOutcome.REJECTED
            message = f"Payment cancellation rejected by bank: {rejection_reason or 'unspecified'}"
        else:
            raise ToolRefusal(
                Rule.SOURCE_INCOMPLETE,
                f"unrecognized ISO 20022 cancellation status code: '{status_code}'",
            )

        return CancellationResponse(
            original_reference=expected_reference,
            reason="Customer request",
            requested_by="customer",
            outcome=outcome,
            rejection_reason=rejection_reason,
            simulated=True,
            message=message,
        )


class MockIso20022Middleware:
    """Mock Core Banking Middleware executing camt.056 and responding with camt.029."""

    def __init__(self, *, reject_references: frozenset[str] = frozenset()) -> None:
        self.reject_references = reject_references
        self.received_requests: list[str] = []

    def exchange(self, request_xml: str) -> str:
        """Parse camt.056 request and synthesize authentic camt.029 response."""
        self.received_requests.append(request_xml)

        root = ET.fromstring(request_xml)
        req = _find_elem(root, "FIToFIPmtCxlReq")
        if req is None:
            raise ValueError("Invalid camt.056 payload: missing FIToFIPmtCxlReq")

        undrlyg = _find_elem(req, "Undrlyg")
        tx_inf = _find_elem(undrlyg, "TxInf") if undrlyg is not None else None

        cxl_id = _find_text(tx_inf, "CxlId")
        orgnl_tx_id = _find_text(tx_inf, "OrgnlTxId")

        # Check if reference is configured for bank rejection
        is_rejected = orgnl_tx_id in self.reject_references
        status_code = "RJCT" if is_rejected else "CNCL"
        reason_code = "LEGL" if is_rejected else "CUST"

        # Build camt.029 XML response
        doc = ET.Element("Document", xmlns=CAMT_029_NS)
        rsltn = ET.SubElement(doc, "RsltnOfInvstgtn")

        # Group Header
        grp_hdr = ET.SubElement(rsltn, "GrpHdr")
        ET.SubElement(grp_hdr, "MsgId").text = f"RESP-{cxl_id}"
        ET.SubElement(grp_hdr, "CreDtTm").text = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Resolved Case matching outbound CxlId
        rslvd_case = ET.SubElement(rsltn, "RslvdCase")
        ET.SubElement(rslvd_case, "Id").text = cxl_id

        # Cancellation Details
        cxl_dtls = ET.SubElement(rsltn, "CxlDtls")
        tx_and_sts = ET.SubElement(cxl_dtls, "TxInfAndSts")
        ET.SubElement(tx_and_sts, "CxlStsId").text = status_code

        rsn_inf = ET.SubElement(tx_and_sts, "CxlStsRsnInf")
        rsn = ET.SubElement(rsn_inf, "Rsn")
        ET.SubElement(rsn, "Cd").text = reason_code

        resp_undrlyg = ET.SubElement(tx_and_sts, "Undrlyg")
        resp_tx = ET.SubElement(resp_undrlyg, "TxInf")
        ET.SubElement(resp_tx, "OrgnlTxId").text = orgnl_tx_id

        return ET.tostring(doc, encoding="utf-8", xml_declaration=True).decode("utf-8")
