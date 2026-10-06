# T-301: Bounded support agent with policy retrieval

| | |
|---|---|
| Wave | 3 |
| Branch | `feat/t301-live-verification` |
| Depends on | T-204, T-206 |
| Blocked by | — (unblocked: keys active, T-206 merged) |
| Model | `Qwen/Qwen3.6-35B-A3B-FP8` (Hetzner) |
| Can run in parallel | no |
| References | decision 15, decision 39; DESIGN.md 4.0; TSD-016 |
| Status | **done** (evidence: `reports/eval/T-301-2026-10-05-live-agent-evidence.md`) |

**Goal.** The bounded generative System 2 worker for stuck payments, grounded in governed tools, the versioned playbook and policy retrieval; the model proposes, but never authorizes.

**Inputs.** the hub, the tools, policy documents for retrieval, the playbook `playbooks/stuck-payments.yaml` (decision 24); the agent's model is open Qwen on Hetzner (`Qwen/Qwen3.6-35B-A3B-FP8`).

**Outputs.** one support-agent implementation of the hub's existing `SupportAgent` interface (`calvino.hub.llm_agent.LlmAgent`), policy retrieval with cited evidence, versioned prompts (`prompts/support-agent-v1.yaml`), redacted provider inputs, and Spanish and Portuguese replies verified under the verifier cascade.

**Verification evidence.** Tested live on Hetzner (`Qwen/Qwen3.6-35B-A3B-FP8`) and recorded in [`reports/eval/T-301-2026-10-05-live-agent-evidence.md`](../../reports/eval/T-301-2026-10-05-live-agent-evidence.md):
- **Spanish turn**: 80.2s generation latency, 100% pass on all 6 deterministic code checks (`amounts-dates-merchants-match`, `stated-status-matches-record`, `claimed-actions-read-back`, `no-other-customer-data`, `reply-in-customer-language`, `no-money-movement-promise`).
- **Portuguese turn**: 102.8s generation latency, 100% pass on all 6 deterministic code checks.
- Model arguments carry no session tokens; all citable facts match verified tool results.
- Verification script reproducible via `python scripts/verify_live_support_agent.py`.
