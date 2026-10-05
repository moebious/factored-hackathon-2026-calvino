"""The MCP server exposing the bank tools (TSD-002), built with the official MCP Python SDK.

Calvino's only path to bank data and actions. No tool takes a customer or session argument: the
session comes from ``resolve_session``, which the hub supplies and which reads the server's request
context (for example a header the hub sets on the HTTP transport). A refusal reaches the client as a
tool error that starts with its rule id, for example ``TOOL-NOT-OWNER: ...``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import TypeVar

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from calvino.tools.contracts import (
    Account,
    AccountEntry,
    CancellationResponse,
    CustomerSummary,
    Investigation,
    PaymentStatus,
    RetryResult,
)
from calvino.tools.errors import ToolRefusal
from calvino.tools.service import BankTools
from calvino.tools.session import Session, SessionResolver

T = TypeVar("T")

TOOL_NAMES = (
    "get_customer_summary",
    "list_accounts",
    "get_account_entries",
    "get_entry_detail",
    "get_payment_status",
    "list_problem_transactions",
    "request_cancellation",
    "retry_payment",
    "open_investigation",
    "get_investigation_status",
)


def create_server(
    tools: BankTools, resolve_session: SessionResolver, name: str = "calvino-bank"
) -> MCPServer:
    """Build the server. ``resolve_session`` is the only way a customer reaches a tool."""
    server = MCPServer(name)

    def run(ctx: Context, call: Callable[[Session | None], T]) -> T:
        try:
            return call(resolve_session(ctx))
        except ToolRefusal as refusal:
            raise ToolError(str(refusal)) from refusal

    @server.tool()
    def get_customer_summary(ctx: Context) -> CustomerSummary:
        """Signed-in customer details; some source fields may be unavailable."""
        return run(ctx, lambda s: tools.get_customer_summary(s))

    @server.tool()
    def list_accounts(ctx: Context) -> list[Account]:
        """The signed-in customer's accounts or linked-product projections."""
        return run(ctx, lambda s: tools.list_accounts(s))

    @server.tool()
    def get_account_entries(
        ctx: Context, account_id: str, date_from: date | None = None, date_to: date | None = None
    ) -> list[AccountEntry]:
        """Entries on one of the customer's accounts, optionally between two booking dates."""
        return run(ctx, lambda s: tools.get_account_entries(s, account_id, date_from, date_to))

    @server.tool()
    def get_entry_detail(ctx: Context, entry_reference: str) -> AccountEntry:
        """One entry of the customer's, by its entry reference."""
        return run(ctx, lambda s: tools.get_entry_detail(s, entry_reference))

    @server.tool()
    def get_payment_status(ctx: Context, entry_reference: str) -> PaymentStatus:
        """The status of one payment and, when known, why."""
        return run(ctx, lambda s: tools.get_payment_status(s, entry_reference))

    @server.tool()
    def list_problem_transactions(
        ctx: Context, date_from: date | None = None, date_to: date | None = None
    ) -> list[AccountEntry]:
        """The customer's Declined, Pending and Reversed transactions, optionally by date."""
        return run(ctx, lambda s: tools.list_problem_transactions(s, date_from, date_to))

    @server.tool()
    def request_cancellation(
        ctx: Context,
        entry_reference: str,
        idempotency_key: str,
        confirmation_token: str,
        reason: str = "Customer request",
    ) -> CancellationResponse:
        """Cancel a Pending transfer (simulated). Needs a hub-issued confirmation token."""
        return run(
            ctx,
            lambda s: tools.request_cancellation(
                s, entry_reference, idempotency_key, confirmation_token, reason
            ),
        )

    @server.tool()
    def retry_payment(
        ctx: Context, entry_reference: str, idempotency_key: str, confirmation_token: str
    ) -> RetryResult:
        """Retry a Declined transfer as a new payment (simulated). Needs a confirmation token."""
        return run(
            ctx,
            lambda s: tools.retry_payment(s, entry_reference, idempotency_key, confirmation_token),
        )

    @server.tool()
    def open_investigation(
        ctx: Context,
        entry_reference: str,
        reason: str,
        idempotency_key: str,
        confirmation_token: str,
    ) -> Investigation:
        """Open a case for a person to review. Needs a hub-issued confirmation token."""
        return run(
            ctx,
            lambda s: tools.open_investigation(
                s, entry_reference, reason, idempotency_key, confirmation_token
            ),
        )

    @server.tool()
    def get_investigation_status(ctx: Context, case_id: str) -> Investigation:
        """The status and next step of the customer's own case."""
        return run(ctx, lambda s: tools.get_investigation_status(s, case_id))

    return server
