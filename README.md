# Project Calvino

![License: MIT](https://img.shields.io/badge/license-MIT-blue)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)

**An evolutionary, AI-powered decision engine for banking customer service: it answers payment questions safely, takes an action only when the policy allows it, and hands investigations to people with a complete file.**

Models suggest, a versioned policy decides, people approve what matters, and their decisions improve the next version. Why each of those words: [DESIGN.md 2](docs/DESIGN.md#2-thesis). Built for the [Factored AI & Data Hackathon 2026](https://www.factored.ai/careers/ai-data-hackathon).

## The workflow: stuck payments

| Stage | The customer gets |
|---|---|
| **Explain** | the status of a declined, pending or reversed payment, from the bank's records |
| **Clarify** | one question, or a pick-list of their problem payments; nothing runs on a guess |
| **Act** | a cancelled or retried transfer, only when the policy allows it (simulated) |
| **Investigate** | a case number, while a person gets the full case file |
| **Follow up** | a verified answer to "how is my case?" |

```mermaid
flowchart LR
    M([Customer message]) --> R[Hard rules]
    R -->|none fires| L[Laya<br/>probabilities]
    L --> P[Policy<br/>verdict]
    P -->|answer or act| A[Agent and<br/>bank tools]
    A --> V[Verifier]
    V -->|passes| Y([Verified reply])
    P -->|unclear| Q([One clarifying question])
    R -->|a rule fires| H([A person, with the case file])
    P -->|needs a person| H
    V -->|fails twice| H
    H -.->|decisions become labels| N[Next policy version]
```

Disputes and fraud always go to a person, and Calvino never moves money. One customer's journey through every part: [DESIGN.md 6.2](docs/DESIGN.md#62-one-journey-end-to-end).

## Quick start

Python 3.11+ and [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/moebious/factored-hackathon-2026-calvino.git
cd factored-hackathon-2026-calvino
uv sync                                                                   # package and dev tools from uv.lock
uv run pytest                                                             # tests: no network, GPU or dataset
uv run python scripts/validate_data_contracts.py --dir tests/fixtures/lakehouse   # audit the synthetic tables
```

Run the demo (deployment skeleton, [docs/DEPLOY.md](docs/DEPLOY.md) for the full path):

```bash
CALVINO_DEMO_PASSCODE=<passcode> uv run python -m calvino.api             # demo API on :7860 (needs `uv pip install laya`)
docker build -t calvino-demo:local . && docker run -p 7860:7860 -v calvino-data:/data calvino-demo:local   # the Space image
cd frontend && npm install && BACKEND_URL=http://127.0.0.1:7860 npm run dev                               # demo frontend on :3000
```

## Start here

[HANDOFF.md](docs/HANDOFF.md) for the current state, [DESIGN.md](docs/DESIGN.md) for the architecture, [AGENTS.md](AGENTS.md) for how to work in this repository (small squash-merged pull requests, Conventional Commits).

## Credits and license

By Kevin Vicent. Thanks to [Factored](https://www.factored.ai) for the challenge and the synthetic LATAM Bank dataset, and to Convai Innovations for [Laya](https://huggingface.co/convaiinnovations/laya). [MIT](LICENSE) © 2026 Kevin Vicent; Laya is Apache 2.0.
