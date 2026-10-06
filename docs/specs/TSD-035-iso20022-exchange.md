# TSD-035: Governed ISO 20022 Bank-Action Exchange (T-604)

| | |
|---|---|
| Status | proposed |
| Branch | `feat/iso20022-xml` |
| Task | [T-604](../tasks/T-604-iso20022-xml.md) |
| Depends on | T-206 (Cleaned-table adapter), TSD-002 (MCP bank tools) |
| Required by | Wave 3 Core bank-boundary proof (Decision 36) |
| Requirements | PRD FR-8, FR-11; AC-1, AC-6, AC-7, AC-8 |
| Design | DESIGN.md 3.1, 4.2; decisions 9, 12, 26, 36 |

## Purpose

Demonstrate realistic bank middleware integration by mapping a Gate-authorized, confirmation-token-validated stuck payment cancellation into an official **ISO 20022 `camt.056.001.08` (Payment Cancellation Request)** XML message, executing through a mock ISO 20022 middleware endpoint, and deterministically verifying the incoming **ISO 20022 `camt.029.001.09` (Resolution of Investigation / Cancellation Response)** XML before reporting the verified outcome to the customer.

## Background & Architectural Boundaries (Decision 36)

1. **MCP vs. ISO 20022 Separation**:
   - MCP (`calvino.tools`) is the governed internal agent/hub tool-calling boundary with typed Python contracts and confirmation tokens.
   - ISO 20022 XML is the bank-facing inter-bank/core middleware message format.
   - An ISO 20022 status code (`RJCT`, `ACCP`, `PDNG`) is **never** used as a Calvino policy routing verdict; Calvino's policy verdicts (`allow`, `ask`, `block`) are distinct from payment processing lifecycle states.
2. **Zero Hallucination / Deterministic Mapping**:
   - No LLM writes XML or parses banking payloads. Mapping from Calvino's typed contracts to XML elements is 100% deterministic and validated against the pinned XML schema profile.
3. **Fail-Closed Verification**:
   - Any schema error, signature/token mismatch, unrecognized response status, or cross-account data leakage fails closed into an audit refusal, without executing state changes.

## Selected ISO 20022 Message Profile

We pin the following standard ISO 20022 schemas for stuck payment cancellations:

1. **Outbound Request: `camt.056.001.08` (`FIToFIPaymentCancellationRequest`)**:
   - Root: `<Document><FIToFIPmtCxlReq>...</FIToFIPmtCxlReq></Document>`
   - `GrpHdr/MsgId`: Unique ISO message ID scoped to session (`CALVINO-CXL-<idempotency_key>`)
   - `GrpHdr/CreDtTm`: ISO 8601 timestamp in UTC
   - `Undrlyg/TxInf/CxlId`: Cancellation tracking ID
   - `Undrlyg/TxInf/OrgnlTxId`: Target entry reference (`entry_reference`, e.g. `E-MX-002`)
   - `Undrlyg/TxInf/OrgnlTxRef/Amt/InstdAmt`: Exact amount and ISO 4217 currency (`amount`, `currency`)
   - `Undrlyg/TxInf/CxlRsnInf/Rsn/Prtry`: Cancellation reason code (`CUST_REQ`, `DUPL_PMT`, etc.)
   - `Assgnr/Pty/Id/OrgId/Othr/Id`: Authenticated customer ID (`customer_id`)

2. **Inbound Response: `camt.029.001.09` (`ResolutionOfInvestigation`)**:
   - Root: `<Document><RsltnOfInvstgtn>...</RsltnOfInvstgtn></Document>`
   - `RslvdCase/Id`: Matches outbound cancellation ID
   - `CxlDtls/TxInfAndSts/CxlStsId`: Result status (`CNCL` = Cancelled/Accepted, `RJCT` = Rejected)
   - `CxlDtls/TxInfAndSts/CxlStsRsnInf/Rsn/Cd`: Bank reason code (e.g. `CUST` = Requested by customer, `LEGL` = Legal block)
   - `Undrlyg/TxInf/OrgnlTxId`: Read-back target transaction ID

## Module Architecture & Interfaces

New package module: `calvino.iso20022`

```python
class Iso20022Middleware:
    """Mock ISO 20022 Core Banking Middleware."""

    def exchange(self, request_xml: str) -> str:
        """Process camt.056 XML and return camt.029 XML response."""
        ...


class Iso20022CancellationClient:
    """Governed client executing cancellations over ISO 20022 XML middleware."""

    def build_cancellation_request_xml(
        self,
        *,
        entry_reference: str,
        amount: Decimal,
        currency: str,
        customer_id: str,
        idempotency_key: str,
        reason: str,
    ) -> str: ...

    def parse_and_verify_cancellation_response(
        self,
        response_xml: str,
        expected_reference: str,
        expected_idempotency_key: str,
    ) -> CancellationResponse: ...
```

## Security & Conformance Checks

1. **Schema & Well-Formedness Validation**: Validates XML against pinned element tags and ISO standards.
2. **Read-Back Reference Binding**: Asserts read-back `OrgnlTxId` in response matches outbound target exactly.
3. **Correlation Tracking**: Ensures response `RslvdCase/Id` correlates directly with the request message ID.
4. **Semantic Refusal on Bank Rejection**: If middleware returns rejection (`RJCT`), maps gracefully to `CancellationOutcome.REJECTED` with the bank's rejection reason.
5. **Fail-Closed on Unparseable XML or Mismatches**: Any XML syntax error, missing mandatory tag, or reference divergence raises `ToolRefusal(Rule.SOURCE_INCOMPLETE)`.

## Acceptance Criteria

1. **AC-ISO-1 (Outbound XML Conformance)**: Produces valid `camt.056.001.08` XML containing exact customer ID, original reference, decimal amount, ISO 4217 currency, and timestamp.
2. **AC-ISO-2 (Inbound XML Resolution)**: Parses valid `camt.029.001.09` XML, asserting message correlation and target reference read-back.
3. **AC-ISO-3 (Semantic Protection)**: Blocks mismatched references, unexpected bank rejection codes, and tampered response IDs fail-closed.
4. **AC-ISO-4 (Full Gate Integration Test)**: End-to-end integration test demonstrating Gate confirmation token consumption, ISO XML dispatch, middleware response, and `CancellationResponse` generation.
