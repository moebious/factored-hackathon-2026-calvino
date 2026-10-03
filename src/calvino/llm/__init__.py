"""LLM client and providers (TSD-008): the provider-agnostic chat interface, an
OpenAI-compatible adapter and the Hetzner configuration.

This package is the external model boundary (DESIGN 7), and Laya is deliberately not in it.
Laya is System 1 classification whose calibrated probabilities are an *input* to the policy
(TSD-005); this is System 2 language work, downstream of the policy, whose output is text a
verifier checks. Inference splits along that line, not along "anything that runs a model", so
moving Laya here would bury the policy's main input under this package's name.

Public API:
- ChatClient, ChatRequest, ChatResponse, Role, Message: the seam every language
  call goes through, with no provider in sight.
- assert_distinct_families: refuses a judge from the agent's model family
  (decision 20).
- OpenAiCompatibleClient: any OpenAI-compatible /chat/completions endpoint, with
  a timeout, retries on 429 and 5xx, and a requests-per-window limiter.
- hetzner_client_from_env: the agent-role client, configured from the environment.
"""
