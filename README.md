# Project Calvino

![Status: build phase](https://img.shields.io/badge/status-build%20phase-orange)
![License: MIT](https://img.shields.io/badge/license-MIT-blue)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)

**An evolutionary, AI-powered decision engine for banking customer service: it answers payment questions safely, takes an action only when the policy allows it, and hands investigations to people with a complete file.**

Built for the [Factored AI & Data Hackathon 2026](https://www.factored.ai/careers/ai-data-hackathon).

## Why "evolutionary, AI-powered decision engine"

- **Decision engine.** Every consequential choice (who handles a request, whether an action may run, when a person takes over) is a verdict from a versioned, deterministic policy, not from model prose. The same inputs and policy version always give the same verdict, and every verdict is logged and can be replayed for audit.
- **AI-powered.** Two kinds of models feed it without deciding: Laya, a self-hosted classifier, gives calibrated probabilities (what the customer wants, whether it is clear, whether a person is needed, whether the message is manipulative), and an LLM writes the replies, checked before any customer sees them.
- **Evolutionary.** It improves from its own operation: people's approvals and corrections become labels, labels recalibrate the model and the thresholds, and each change ships as a new policy version only after it is replayed against past decisions and evaluated. It evolves version by version, under human control; it never rewrites itself.

## The workflow: stuck payments

A customer's payment was declined, is pending, or was reversed, and they ask where their money is. Transactional contacts are 35% of calls, and 8% of transactions end in one of those statuses `[measured]`.

| Stage | The customer gets | Decided by |
|---|---|---|
| **Explain** | the status from the bank's records and the next step | hard rules, Laya, the policy; read-only tools; a verified reply |
| **Clarify** | one question, or a pick-list of their problem payments | Laya's confidence; nothing runs on a guess |
| **Act** | cancel a pending transfer or retry a declined one (simulated) | a policy check before every action: allow, ask a person, or refuse |
| **Investigate** | a case number; a person gets the full case file | a durable case that survives restarts |
| **Follow up** | a verified answer to "how is my case?" | the case resumes from its saved state |

Disputes, unrecognised charges and fraud go to a person. Calvino never refunds or moves money. People already resolve 91.5% of these calls on first contact `[measured]`, so the goal on calls is to match them with zero unsafe outcomes at lower time and cost; the improvement is in investigations. One customer's journey through every part: [DESIGN.md 6.2](docs/DESIGN.md#62-one-journey-end-to-end).

## How it works

| Who | Does | Never |
|---|---|---|
| **Policy** (deterministic code) | hard rules first, then thresholds on calibrated probabilities; every verdict logged and replayable | depends on model prose |
| **[Laya](https://huggingface.co/convaiinnovations/laya)** (self-hosted) | typed, calibrated answers: workflow, intent, clarity, needs a person, injection | generates text |
| **LLM** (open models) | the agent's replies, checked by a judge from another model family | authorizes an action |
| **People** | approvals, investigations, disputes, policy changes | are bypassed on a consequential action |

Tools reach the bank only through MCP adapters with ISO 20022-aligned contracts; the customer's session never passes through a model. Design: [DESIGN.md](docs/DESIGN.md); decisions: [DECISIONS.md](docs/DECISIONS.md).

## Status

| Built and tested | In progress | Planned |
|---|---|---|
| policy engine (`calvino.policy`) | verifier, deployment skeleton | the hub (LangGraph) and support agent |
| MCP bank tools (`calvino.tools`) | Laya service and calibration | customer app and operator console |
| data contracts and audit (`calvino.data`), passed on the full data | message set and evaluation | the evaluation with a bare-LLM comparison |

Progress per task: [docs/tasks/](docs/tasks/README.md). Changes: [CHANGELOG.md](CHANGELOG.md).

## Quick start

Python 3.11+ and [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/moebious/factored-hackathon-2026-calvino.git
cd factored-hackathon-2026-calvino
uv sync                                                                   # package and dev tools from uv.lock
uv run pytest                                                             # tests: no network, GPU or dataset
uv run python scripts/validate_data_contracts.py --dir tests/fixtures/lakehouse   # audit the synthetic tables
```

The dataset is read through environment variables and never committed. The customer app is not runnable yet.

## Documentation

| Start here | Then |
|---|---|
| [HANDOFF.md](docs/HANDOFF.md): current state and next actions | [PRD.md](docs/PRD.md), [BRD.md](docs/BRD.md): requirements |
| [DESIGN.md](docs/DESIGN.md): architecture, governance, evaluation | [DATA.md](docs/DATA.md): the dataset and its known defects |
| [AGENTS.md](AGENTS.md): how to work in this repository | [specs/](docs/specs/README.md), [tasks/](docs/tasks/README.md), [ROADMAP.md](docs/ROADMAP.md), [PLAN.md](docs/PLAN.md) |

Claims carry evidence labels: `[measured]`, `[vendor]`, `[read from chart]`, `[hypothesis]`.

## Contributing

Small pull requests, squash-merged, one worktree per branch, Conventional Commits; the rules for people and coding agents are in [AGENTS.md](AGENTS.md).

## Credits and license

By Kevin Vicent. Thanks to [Factored](https://www.factored.ai) for the challenge and the synthetic LATAM Bank dataset, and to Convai Innovations for [Laya](https://huggingface.co/convaiinnovations/laya). The name comes from Italo Calvino's *Invisible Cities*: each part is a self-contained city that the hub knows only through the accounts it receives. Sources: [DESIGN.md, References](docs/DESIGN.md#references).

[MIT](LICENSE) © 2026 Kevin Vicent. Third-party models keep their licenses (Laya: Apache 2.0).
