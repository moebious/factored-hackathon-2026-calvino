"""MCP tools and the bank adapters (TSD-002): Calvino's only path to bank data and actions;
ownership and eligibility are checked here, outside any model.
"""

from calvino.tools.adapter import BankAdapter
from calvino.tools.confirmation import (
    ConfirmationVerifier,
    FakeConfirmationVerifier,
    HmacConfirmationVerifier,
    confirmation_key_from_env,
)
from calvino.tools.dataset import DatasetAdapter
from calvino.tools.errors import ConfigurationError, Rule, ToolRefusal
from calvino.tools.server import TOOL_NAMES, create_server
from calvino.tools.service import BankTools
from calvino.tools.session import Session, SessionResolver

__all__ = [
    "TOOL_NAMES",
    "BankAdapter",
    "BankTools",
    "ConfigurationError",
    "ConfirmationVerifier",
    "DatasetAdapter",
    "FakeConfirmationVerifier",
    "HmacConfirmationVerifier",
    "Rule",
    "Session",
    "SessionResolver",
    "ToolRefusal",
    "confirmation_key_from_env",
    "create_server",
]
