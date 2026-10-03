"""LLM client and providers (TSD-008): the provider-agnostic chat interface, an
OpenAI-compatible adapter and the Hetzner configuration.

This package is the external model boundary (DESIGN 7), and Laya is deliberately not in it.
Laya is System 1 classification whose calibrated probabilities are an *input* to the policy
(TSD-005); this is System 2 language work, downstream of the policy, whose output is text a
verifier checks. Inference splits along that line, not along "anything that runs a model", so
moving Laya here would bury the policy's main input under this package's name.

Public API:
- ChatClient, ChatRequest, ChatResponse, Role, Message, MessageRole, ReasoningEffort: the seam
  every language call goes through, with no provider in sight.
- assert_distinct_families, model_family: refuse a judge from the agent's model family
  (decisions 20 and 28).
- OpenAiCompatibleClient, RateLimiter, client_from_env: any OpenAI-compatible
  /chat/completions endpoint, with a timeout, retries on 429 and 5xx, and a limiter.
- hetzner_client_from_env, judge_client_from_env, clients_from_env: the two role clients, built
  from the environment.
- load_providers, DEFAULT_PROVIDERS_PATH, configuration_problems, verify_catalogue: the
  committed record of which model answers which role, and the checks against it.
- LlmError and its subclasses, each carrying a stable rule id.

Importing this package configures nothing: no client is built and no provider is contacted until
one is asked for.
"""

from calvino.llm.contracts import (
    ChatClient,
    ChatRequest,
    ChatResponse,
    Message,
    MessageRole,
    ReasoningEffort,
    Role,
    assert_distinct_families,
    model_family,
)
from calvino.llm.errors import (
    LlmConfigurationError,
    LlmError,
    LlmRateLimited,
    LlmResponseError,
    LlmRule,
    LlmTimeout,
    LlmTruncated,
    LlmUnavailable,
)
from calvino.llm.hetzner import (
    HETZNER_BASE_URL,
    HETZNER_REQUESTS_PER_WINDOW,
    LlmClients,
    clients_from_env,
    hetzner_client_from_env,
    judge_client_from_env,
)
from calvino.llm.openai_compat import OpenAiCompatibleClient, RateLimiter, client_from_env
from calvino.llm.providers import (
    DEFAULT_PROVIDERS_PATH,
    ProviderFile,
    configuration_problems,
    load_providers,
)
from calvino.llm.verify import unrecorded, verify_catalogue

__all__ = [
    "DEFAULT_PROVIDERS_PATH",
    "HETZNER_BASE_URL",
    "HETZNER_REQUESTS_PER_WINDOW",
    "ChatClient",
    "ChatRequest",
    "ChatResponse",
    "LlmClients",
    "LlmConfigurationError",
    "LlmError",
    "LlmRateLimited",
    "LlmResponseError",
    "LlmRule",
    "LlmTimeout",
    "LlmTruncated",
    "LlmUnavailable",
    "Message",
    "MessageRole",
    "OpenAiCompatibleClient",
    "ProviderFile",
    "RateLimiter",
    "ReasoningEffort",
    "Role",
    "assert_distinct_families",
    "client_from_env",
    "clients_from_env",
    "configuration_problems",
    "hetzner_client_from_env",
    "judge_client_from_env",
    "load_providers",
    "model_family",
    "unrecorded",
    "verify_catalogue",
]
