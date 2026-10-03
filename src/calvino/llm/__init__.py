"""LLM client and providers (TSD-008): the provider-agnostic chat interface, an
OpenAI-compatible adapter and the Hetzner configuration.

Public API:
- ChatClient, ChatRequest, ChatResponse, Role, Message: the seam every language
  call goes through, with no provider in sight.
- assert_distinct_families: refuses a judge from the agent's model family
  (decision 20).
- OpenAiCompatibleClient: any OpenAI-compatible /chat/completions endpoint, with
  a timeout, retries on 429 and 5xx, and a requests-per-window limiter.
- hetzner_client_from_env: the agent-role client, configured from the environment.
"""
