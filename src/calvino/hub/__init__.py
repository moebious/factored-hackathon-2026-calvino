"""Calvino hub (TSD-009): System 1.5 for the stuck-payments workflow.

Wires the policy engine, MCP tools, verifier and Laya into the five stages of DESIGN 6.1
(explain, clarify, act under the Gate, investigate, follow up) as one LangGraph graph with a
checkpointer and ``interrupt()`` for the human steps. Every decision is logged.

Public API:
- Playbook, StatusGuidance, load_playbook: the versioned playbook file (decision 24) that
  feeds both the agent's guidance and the verifier's "valid next step" criterion.
- SupportAgent, AgentRequest, AgentDraft, ToolCall, ScriptedAgent: the language work behind
  an interface (decision 20); the session token never reaches a request.
- TrustedSessionIssuer: demo personas sign in through the hub; chat never types an identity.
- HubStage, HubState: the graph's stage enum and checkpointer-persisted state.
"""

from calvino.hub.agent import (
    AgentDraft,
    AgentRequest,
    ScriptedAgent,
    SupportAgent,
    ToolCall,
)
from calvino.hub.playbook import (
    DEFAULT_PLAYBOOK_PATH,
    PLAYBOOK_ACTIONS,
    WORKFLOW_STATUSES,
    Playbook,
    StatusGuidance,
    load_playbook,
)
from calvino.hub.sessions import DEFAULT_SESSION_TTL, TrustedSessionIssuer
from calvino.hub.state import HubStage, HubState

__all__ = [
    "DEFAULT_PLAYBOOK_PATH",
    "DEFAULT_SESSION_TTL",
    "PLAYBOOK_ACTIONS",
    "WORKFLOW_STATUSES",
    "AgentDraft",
    "AgentRequest",
    "HubStage",
    "HubState",
    "Playbook",
    "ScriptedAgent",
    "StatusGuidance",
    "SupportAgent",
    "ToolCall",
    "TrustedSessionIssuer",
    "load_playbook",
]
