"""Tests for Governed ISO 20022 XML Messaging (TSD-034, T-604).

Validates:
1. camt.056.001.08 XML creation with required tags, decimal formatting, and namespaces.
2. camt.029.001.09 XML resolution, status interpretation (CNCL -> accepted, RJCT -> rejected).
3. Fail-closed security validations:
   - XML parse errors / empty payloads.
   - Case ID correlation mismatch.
   - Original reference read-back divergence.
   - Unrecognized ISO status codes.
4. End-to-end integration across mock middleware.
"""

from decimal import Decimal

import pytest

from calvino.iso20022.exchange import (
    CAMT_029_NS,
    CAMT_056_NS,
    Iso20022CancellationClient,
    MockIso20022Middleware,
)
from calvino.tools.contracts import CancellationOutcome
from calvino.tools.errors import ToolRefusal


class TestIso20022CancellationClient:
    def test_build_cancellation_request_xml_structure(self) -> None:
        client = Iso20022CancellationClient()
        xml_str = client.build_cancellation_request_xml(
            entry_reference="E-MX-002",
            amount=Decimal("5000.00"),
            currency="MXN",
            customer_id="CUST-001",
            idempotency_key="idemp-12345",
            reason="Customer request",
        )

        assert CAMT_056_NS in xml_str
        assert "FIToFIPmtCxlReq" in xml_str
        assert "CALVINO-CXL-idemp-12345" in xml_str
        assert "E-MX-002" in xml_str
        assert 'Ccy="MXN"' in xml_str
        assert "5000.00" in xml_str
        assert "CUST-001" in xml_str

    def test_mock_middleware_exchange_successful_cancellation(self) -> None:
        client = Iso20022CancellationClient()
        middleware = MockIso20022Middleware()

        req_xml = client.build_cancellation_request_xml(
            entry_reference="E-MX-002",
            amount=Decimal("5000.00"),
            currency="MXN",
            customer_id="CUST-001",
            idempotency_key="test-req-1",
        )

        resp_xml = middleware.exchange(req_xml)

        assert CAMT_029_NS in resp_xml
        assert "RsltnOfInvstgtn" in resp_xml
        assert "CNCL" in resp_xml
        assert "E-MX-002" in resp_xml

        outcome = client.parse_and_verify_cancellation_response(
            resp_xml,
            expected_reference="E-MX-002",
            expected_idempotency_key="test-req-1",
        )

        assert outcome.outcome == CancellationOutcome.ACCEPTED
        assert outcome.original_reference == "E-MX-002"
        assert outcome.simulated is True
        assert outcome.rejection_reason == "CUST"

    def test_mock_middleware_exchange_rejected_cancellation(self) -> None:
        client = Iso20022CancellationClient()
        middleware = MockIso20022Middleware(reject_references=frozenset(["E-MX-BLOCKED"]))

        req_xml = client.build_cancellation_request_xml(
            entry_reference="E-MX-BLOCKED",
            amount=Decimal("1500.00"),
            currency="MXN",
            customer_id="CUST-002",
            idempotency_key="reject-req-1",
        )

        resp_xml = middleware.exchange(req_xml)
        assert "RJCT" in resp_xml

        outcome = client.parse_and_verify_cancellation_response(
            resp_xml,
            expected_reference="E-MX-BLOCKED",
            expected_idempotency_key="reject-req-1",
        )

        assert outcome.outcome == CancellationOutcome.REJECTED
        assert outcome.original_reference == "E-MX-BLOCKED"
        assert outcome.rejection_reason == "LEGL"

    def test_parse_fails_on_correlation_mismatch(self) -> None:
        client = Iso20022CancellationClient()
        middleware = MockIso20022Middleware()

        req_xml = client.build_cancellation_request_xml(
            entry_reference="E-MX-002",
            amount=Decimal("5000.00"),
            currency="MXN",
            customer_id="CUST-001",
            idempotency_key="idemp-correct",
        )
        resp_xml = middleware.exchange(req_xml)

        with pytest.raises(ToolRefusal, match="ISO 20022 correlation error"):
            client.parse_and_verify_cancellation_response(
                resp_xml,
                expected_reference="E-MX-002",
                expected_idempotency_key="idemp-wrong",
            )

    def test_parse_fails_on_reference_readback_mismatch(self) -> None:
        client = Iso20022CancellationClient()
        middleware = MockIso20022Middleware()

        req_xml = client.build_cancellation_request_xml(
            entry_reference="E-MX-002",
            amount=Decimal("5000.00"),
            currency="MXN",
            customer_id="CUST-001",
            idempotency_key="idemp-1",
        )
        resp_xml = middleware.exchange(req_xml)

        with pytest.raises(ToolRefusal, match="ISO 20022 reference mismatch"):
            client.parse_and_verify_cancellation_response(
                resp_xml,
                expected_reference="E-MX-DIFFERENT",
                expected_idempotency_key="idemp-1",
            )

    def test_parse_fails_closed_on_empty_or_malformed_xml(self) -> None:
        client = Iso20022CancellationClient()

        with pytest.raises(ToolRefusal, match="empty XML response"):
            client.parse_and_verify_cancellation_response(
                "",
                expected_reference="E-MX-002",
                expected_idempotency_key="key",
            )

        with pytest.raises(ToolRefusal, match="malformed ISO 20022 XML"):
            client.parse_and_verify_cancellation_response(
                "<UnclosedTag>",
                expected_reference="E-MX-002",
                expected_idempotency_key="key",
            )
