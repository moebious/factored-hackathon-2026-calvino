"""Measure how policy versions route a labelled set of messages on live Laya (TSD-021).

``uv run python scripts/measure_routing.py --labels <rows.jsonl> [--policies v2 v3]``

Each row is classified once with the five workflow questions, then routed under every policy file
given (default: v2 and v3) through the same functions the hub uses, ``scores_from_answers`` and
``decide_route``. Rows carry ``needs_person`` (the rubric label) and a ``kind``. The report gives,
per policy, how many routine rows reach the agent and how many needs-a-person rows do, the gates
that stop the rest, and the AUROC of each single signal against the label. Needs ``uv pip install
laya``; no network once the checkpoint is cached. Refuses rows marked as a frozen split: this tool
is for development and confirmation rows, never for the frozen evaluation cases.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from calvino.api.decide import scores_from_answers  # noqa: E402
from calvino.classifiers import LayaAnswer, workflow_questions  # noqa: E402
from calvino.policy import decide_route, load_policy  # noqa: E402
from calvino.records import session_ref_for  # noqa: E402

POLICY_DIR = Path(__file__).resolve().parent.parent / "policy"
FROZEN = frozenset({"test", "frozen"})
FACTS = {
    "session_ref": session_ref_for("measure-routing"),
    "fraud_signal": False,
    "asks_for_human": False,
    "auth_failures": 0,
    "via_regulator": False,
    "vulnerable_customer": False,
}
SIGNALS = {
    "needs_human": lambda s: s["needs_human"],
    "area: dispute or fraud": lambda s: s["workflow_dispute_or_fraud"],
    "intent: talk to a person": lambda s: s["talk_to_person"],
    "injection": lambda s: s["injection"],
}

Classify = Callable[[str], dict[str, LayaAnswer]]


def auroc(scores: Sequence[float], labels: Sequence[bool]) -> float | None:
    """P(a positive outscores a negative), ties half; None when a class is empty."""
    pos = [s for s, y in zip(scores, labels, strict=True) if y]
    neg = [s for s, y in zip(scores, labels, strict=True) if not y]
    if not pos or not neg:
        return None
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


def load_rows(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    for row in rows:
        if row.get("split") in FROZEN:
            raise SystemExit(f"{row.get('id')}: frozen split {row['split']!r}; refusing")
    return rows


def laya_classifier() -> Classify:
    from calvino.api.loader import LayaLoader

    loader = LayaLoader()
    loader.preload()
    questions = workflow_questions()
    return lambda text: {a.question_id: a for a in loader.classify(text, questions)}


def route_all(rows: Sequence[Mapping], answers: Sequence[dict], policy) -> list[tuple[str, str]]:
    """(route, rule id) per row under one policy, via the hub's own functions."""
    out = []
    for answer in answers:
        scores = scores_from_answers(answer, policy.route.confidence_source)
        decision = decide_route(scores, FACTS, policy)
        out.append((decision.route.value, decision.rule_id))
    return out


def summarise(rows: Sequence[Mapping], routes: Sequence[tuple[str, str]]) -> dict:
    routine = [r for row, r in zip(rows, routes, strict=True) if not row["needs_person"]]
    needs = [r for row, r in zip(rows, routes, strict=True) if row["needs_person"]]
    return {
        "routine_to_agents": [sum(r[0] == "agents" for r in routine), len(routine)],
        "needs_person_to_agents": [sum(r[0] == "agents" for r in needs), len(needs)],
        "needs_person_to_human": [sum(r[0] == "human" for r in needs), len(needs)],
        "routine_stopped_by": dict(Counter(r[1] for r in routine if r[0] != "agents")),
        "needs_person_stopped_by": dict(Counter(r[1] for r in needs if r[0] != "agents")),
    }


def measure(rows: Sequence[Mapping], classify: Classify, policies: Mapping[str, object]) -> dict:
    answers = [classify(row["message"]) for row in rows]
    labels = [bool(row["needs_person"]) for row in rows]
    signals = {}
    for name, pick in SIGNALS.items():
        scores = [pick(scores_from_answers(a)) for a in answers]
        signals[name] = auroc(scores, labels)
    best = [
        max(pick(scores_from_answers(a)) for name, pick in SIGNALS.items() if name != "needs_human")
        for a in answers
    ]
    signals["max(area, intent, injection)"] = auroc(best, labels)
    routed = {name: route_all(rows, answers, policy) for name, policy in policies.items()}
    return {
        "n": len(rows),
        "needs_person": sum(labels),
        "auroc": signals,
        "policies": {name: summarise(rows, routes) for name, routes in routed.items()},
        "rows": [
            {
                "id": row["id"],
                "kind": row.get("kind"),
                "needs_person": bool(row["needs_person"]),
                "routes": {name: list(routes[i]) for name, routes in routed.items()},
            }
            for i, row in enumerate(rows)
        ],
    }


def _pct(pair: Sequence[int]) -> str:
    return f"{pair[0]}/{pair[1]} ({100 * pair[0] / pair[1]:.0f}%)" if pair[1] else "n/a"


def render(result: dict, source: str, evidence: str) -> str:
    names = list(result["policies"])
    lines = [
        f"# Routing under policy versions ({date.today().isoformat()})",
        "",
        f"Source `{source}`: n = {result['n']} ({result['needs_person']} labelled needs_person). "
        f"Evidence label: **{evidence}**. Live laya, the hub's own scoring and `decide_route`.",
        "",
        "## Single-signal AUROC against the needs_person label",
        "",
        "| Signal | AUROC |",
        "|---|---|",
    ]
    for name, value in result["auroc"].items():
        lines.append(f"| {name} | {'n/a' if value is None else f'{value:.2f}'} |")
    lines += ["", "## Where rows go", "", "| | " + " | ".join(names) + " |"]
    lines.append("|---|" + "---|" * len(names))
    for label, key in (
        ("routine rows reaching the agent", "routine_to_agents"),
        ("needs-a-person rows reaching the agent", "needs_person_to_agents"),
        ("needs-a-person rows sent to a person", "needs_person_to_human"),
    ):
        cells = " | ".join(_pct(result["policies"][n][key]) for n in names)
        lines.append(f"| {label} | {cells} |")
    for label, key in (
        ("routine rows stopped by", "routine_stopped_by"),
        ("needs-a-person rows stopped by", "needs_person_stopped_by"),
    ):
        cells = " | ".join(
            ", ".join(f"{k} {v}" for k, v in sorted(result["policies"][n][key].items())) or "none"
            for n in names
        )
        lines.append(f"| {label} | {cells} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None, *, classify: Classify | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--policies", nargs="+", default=["v2", "v3"])
    parser.add_argument("--out", type=Path, default=Path("reports/classifiers"))
    parser.add_argument("--tag", default="routing")
    parser.add_argument("--evidence", default="exploratory, team-written rows")
    args = parser.parse_args(argv)
    policies = {v: load_policy(POLICY_DIR / f"{v}.yaml") for v in args.policies}
    result = measure(load_rows(args.labels), classify or laya_classifier(), policies)
    args.out.mkdir(parents=True, exist_ok=True)
    stem = args.out / f"{args.tag}-{date.today().isoformat()}"
    stem.with_suffix(".md").write_text(
        render(result, str(args.labels), args.evidence), encoding="utf-8"
    )
    stem.with_suffix(".json").write_text(
        json.dumps({"source": str(args.labels), "evidence": args.evidence, **result}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {stem}.md and .json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
