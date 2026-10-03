# TSD-011: LLM client and Hetzner provider

| | |
|---|---|
| Status | implemented |
| Branch | `feat/llm-client` |
| Depends on | TSD-000 |
| Required by | T-106 (message drafting), T-301 (support agent), the verifier's batched judge (TSD-004, FR-6) |
| Requirements | FR-6, FR-11, NFR-1, NFR-7, NFR-8 |
| Design | DESIGN.md 4.2, 4.4, 7 (external model boundary) |

## Purpose

The one place Calvino talks to an external language model: a provider-agnostic chat interface, an
OpenAI-compatible adapter, and Hetzner as the first provider for the agent role.

This spec is the plumbing only. It decides no verdict, holds no prompt and reads no customer data;
what the model is asked to write is T-301, and the rubric the judge checks is TSD-004.

## Interfaces

**`ChatClient`** (Protocol, in `calvino.llm.contracts`) is the seam. One method:

- `complete(request: ChatRequest) -> ChatResponse`.

**`ChatRequest`** carries the messages, the `Role` (`agent` or `judge`), an optional `purpose` tag
for logs, `temperature` and `max_tokens`. Nothing else: no tools, no images, no streaming in this
spec.

**`ChatResponse`** carries the text, the `model` the provider reports, prompt and completion token
counts, `finish_reason` and `latency_ms`. `model` is what decision 20 records in every
`DecisionRecord.versions.model`, so replay can name the model that wrote the text.

**`FakeChatClient`** is deterministic, for tests. Tests never reach the network (AGENTS.md).

**`OpenAiCompatibleClient`** (in `calvino.llm.openai_compat`) speaks any OpenAI-compatible
`/chat/completions`: `base_url`, `api_key`, `model`, request timeout, retry count and a
requests-per-window limiter. Failures raise `LlmError` subclasses carrying stable ids, the way tools
carry `TOOL-*` rule ids.

**`calvino.llm.hetzner`** holds the Hetzner specifics: base URL `https://inference.hetzner.com/api/v1`,
a bearer token, and the limits its documentation states `[vendor]`: 10 requests per 60 s per key,
4M input and 100k output tokens per 60 s, HTTP 429 when exceeded. `hetzner_client_from_env()` builds
the agent-role client; the model id is read from the environment and never hardcoded, because
`/v1/models` is the authoritative list and Hetzner says the selection will change.

**`assert_distinct_families(agent_model, judge_model)`** refuses a judge from the same model family
as the agent (decision 20: a judge from the same family tends to pass its family's mistakes). It is
a startup check with a unit test, not a comment.

## Behaviour and data

- **Roles.** Only the agent role is wired to Hetzner now. The judge role is configured separately
  (Hugging Face Inference Providers or OpenRouter) so the family guard above can pass.
- **Fail closed on configuration.** A missing key or model raises `LlmConfigurationError` at startup.
  Keys come from environment variables only, are never logged and never written to the audit log.
- **Rate limiting.** The adapter keeps a sliding-window limiter, defaulting below the documented cap,
  and honours `Retry-After` on 429. It retries 429 and 5xx with backoff, and never retries another
  4xx, which is a request the caller got wrong.
- **Laya is not a candidate for this API.** It is a generative chat endpoint: it returns text, not
  per-option probabilities and entropy, so the calibration TSD-005 relies on cannot be measured on
  it, and `logprobs` is not documented. Laya stays self-hosted and customer text for decisions never
  leaves (NFR-1, decision 2). Recorded in DECISIONS.md as a rejected alternative.
- **Experimental provider.** Hetzner serves the Inference API free of charge, "as is", with no SLA
  and no backups, and says not to use it in production `[vendor]`. Good enough for the demo and for
  T-106 and T-301; not a production dependency. OpenRouter remains the fallback, and the risk is
  recorded rather than designed around.

## Out of scope

- Prompts and message drafting (T-106, T-301) and the verifier's rubric (TSD-004, T-402).
- The bare-LLM ablation (T-303), which needs the same client with a different prompt.
- Embeddings, retrieval and streaming; images, although one served model is multimodal.
- Choosing the judge's provider, which stays open until the verifier needs it.

## Tests and acceptance

- The adapter sends the documented request shape with a bearer token, and reads text, model, usage
  and `finish_reason` from the response.
- 429 is retried and then raises the rate-limit error; 5xx is retried; 400 is not retried; a timeout
  raises the timeout error. All offline, through an injected transport.
- The limiter refuses the request over the cap in a window, with an injected clock.
- `assert_distinct_families` rejects a Qwen judge beside a Qwen agent and accepts a different family.
- A missing key or model raises a configuration error rather than defaulting.
- The model the provider reports reaches `DecisionRecord.versions.model`.
- The judge role is served by a second client, so adding a provider is a constructor call and not a
  code change.

**Done when** the unit tests pass with no network access, a second provider can be added by
constructing the same adapter with a different base URL, and the family guard is tested.
