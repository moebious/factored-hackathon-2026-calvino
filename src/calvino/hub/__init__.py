"""Calvino hub (TSD-009): System 1.5 for the stuck-payments workflow.

Wires the policy engine, MCP tools, verifier and Laya into the five stages of DESIGN 6.1
(explain, clarify, act under the Gate, investigate, follow up) as one LangGraph graph with a
checkpointer and ``interrupt()`` for the human steps. Every decision is logged.

Public API:
- Playbook, StatusGuidance, load_playbook: the versioned playbook file (decision 24) that
  feeds both the agent's guidance and the verifier's "valid next step" criterion.
- SupportAgent, AgentRequest, AgentDraft, ToolCall, ScriptedAgent: the language work behind
  an interface (decision 20); the session token never reaches a request.
- TemplateAgent: the deterministic demo agent (TSD-010, decision 10) — grounded templated
  Spanish replies from the playbook and the verified tool results, until T-301 lands the
  LLM agent.
- TrustedSessionIssuer, DEMO_PERSONAS: demo personas sign in through the hub; chat never
  types an identity.
- HubStage, HubState: the graph's stage enum and checkpointer-persisted state.
- HubDependencies, FraudContext, ConfirmationIssuer, build_hub_graph, STAGE_TOOLS: the
  LangGraph graph wiring the stages together; the session token travels in the invoke
  config, never in the state.
- HubService, HubReply, TraceStep: the demo-facing facade — one call per customer message,
  resume for the parked operator steps, the turn's decision trace for the glass box, and the
  checkpointer on ``CALVINO_DATA_DIR``.
"""

from calvino.hub.agent import (
    AgentDraft,
    AgentRequest,
    ScriptedAgent,
    SupportAgent,
    ToolCall,
)
from calvino.hub.graph import (
    MAX_TOOL_ROUNDS,
    STAGE_TOOLS,
    ConfirmationIssuer,
    FraudContext,
    HubDependencies,
    build_hub_graph,
)
from calvino.hub.playbook import (
    DEFAULT_PLAYBOOK_PATH,
    PLAYBOOK_ACTIONS,
    WORKFLOW_STATUSES,
    Playbook,
    StatusGuidance,
    load_playbook,
)
from calvino.hub.prompts import DEFAULT_PROMPTS_PATH, PROMPT_STAGES, PromptSet, load_prompts
from calvino.hub.service import HubReply, HubService, TraceStep
from calvino.hub.sessions import DEFAULT_SESSION_TTL, DEMO_PERSONAS, TrustedSessionIssuer
from calvino.hub.state import HubStage, HubState
from calvino.hub.template_agent import TemplateAgent

__all__ = [
    "DEFAULT_PLAYBOOK_PATH",
    "DEFAULT_PROMPTS_PATH",
    "DEFAULT_SESSION_TTL",
    "DEMO_PERSONAS",
    "MAX_TOOL_ROUNDS",
    "PLAYBOOK_ACTIONS",
    "PROMPT_STAGES",
    "STAGE_TOOLS",
    "WORKFLOW_STATUSES",
    "AgentDraft",
    "AgentRequest",
    "ConfirmationIssuer",
    "FraudContext",
    "HubDependencies",
    "HubReply",
    "HubService",
    "HubStage",
    "HubState",
    "Playbook",
    "PromptSet",
    "ScriptedAgent",
    "StatusGuidance",
    "SupportAgent",
    "TemplateAgent",
    "ToolCall",
    "TraceStep",
    "TrustedSessionIssuer",
    "build_hub_graph",
    "load_playbook",
    "load_prompts",
]
