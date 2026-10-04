"""The evaluation report writer (TSD-013): fixed sections, honest numbers.

Renders one run into markdown (the human report) and JSON (the machine
results), in the section order the spec fixes: run header, headline table,
oracle agreement and gold-subset agreement, baseline comparison, language
slices and the flip table, adversarial results, ablation, judge
validation, repeated-run variability, error analysis, limitations.

Two honesty rules drive every line. Every rate carries its numerator,
denominator and an evidence label (``offline`` / ``simulated`` /
``projected``), and an undefined rate renders ``not defined``, never a
number. Every gated part renders ``not run: <blocker>`` from the blocker
its result object carries, so a report is always complete whether or not
keys were present. Baseline figures are quoted with the labels their
sources carry (DESIGN.md and ``reports/baseline/complaints.csv``, both
``[measured]``); investigation savings are **projected only** and no
number is invented for them. The writer is pure: it renders what the run
hands it and reads no clock, no environment and no network.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass

from calvino.evaluation.ablation import Ablation
from calvino.evaluation.judge_validation import JudgeConfusion
from calvino.evaluation.metrics import (
    Cost,
    Rate,
    attempt_rate,
    by_slice,
    containment,
    cost,
    errored,
    escalation_quality,
    latency,
    outcome_agreement,
    safe_resolution,
    scored,
    unsafe_outcomes,
)
from calvino.evaluation.runner import CaseResult

# The report's section headings, in the fixed order (TSD-013 Report).
SECTIONS = (
    "Run header",
    "Headline",
    "Oracle agreement",
    "Baseline comparison",
    "Language slices",
    "Adversarial results",
    "Ablation",
    "Judge validation",
    "Repeated-run variability",
    "Error analysis",
    "Limitations",
)

# The human baselines, quoted with the labels their sources carry.
# DESIGN.md "Baselines": Transaccional calls resolve on first contact
# 91.5% of the time [measured].
HUMAN_FIRST_CONTACT_RESOLUTION = 0.915
# reports/baseline/complaints.csv, Transactions category [measured]:
# sla_breached_share 0.2017 over n=13,580; still_open 10,124 of 13,580.
COMPLAINT_SLA_BREACHED_SHARE = 0.2017
COMPLAINT_SLA_BREACHED_N = 13_580
COMPLAINT_STILL_OPEN_SHARE = 0.745
# The data cannot link a call to its transaction, so investigation
# savings stay projected; the report never states a number for them.

GOLD_BLOCKER = "the T-103 gold sheet is unfilled (labels pending hand-labelling)"

_NOT_DEFINED = "not defined"


@dataclass(frozen=True)
class RunHeader:
    """The versions and labels every number in the report travels with."""

    run_date: str  # ISO date, from the CLI (the writer reads no clock)
    git_sha: str
    suite: str
    repeats: int
    evidence_label: str  # "offline" / "simulated" / "projected" for this run
    policy_version: str
    playbook_version: str
    rubric_version: str  # the rubric ref, e.g. "customer-answer@1"
    judge_prompt_version: int
    oracle_version: str
    laya_version: str | None  # None when the run did not read one
    agent_model: str | None  # None under the TemplateAgent / without keys
    judge_model: str | None
    # Which components actually answered, not which keys were present (TSD-016): a run with
    # keys in the environment can still have been scored on the template.
    agent: str = "TemplateAgent"
    agent_prompt_version: str | None = None
    hub_judge: str = "none: judged criteria are not run"
    llm_priced: bool = True  # False: tokens were used by a role with no price on record


@dataclass(frozen=True)
class RunReport:
    """Everything one run produced; the writer renders exactly this."""

    header: RunHeader
    results: tuple[CaseResult, ...]
    determinism: tuple[str, ...]  # EvaluationRunner.determinism_findings
    judge: JudgeConfusion
    ablation: Ablation
    gold_agreement: Rate | None = None  # oracle vs the hand-labelled gold subset
    gold_blocker: str | None = GOLD_BLOCKER


def _rate_cell(rate: Rate) -> str:
    """One rate as "num/den (xx.x%)" or "not defined", never a bare float."""
    if rate.value is None:
        return f"{_NOT_DEFINED} (n={rate.denominator})"
    return f"{rate.numerator}/{rate.denominator} ({rate.value:.1%})"


def _ms(value: float | None) -> str:
    return _NOT_DEFINED if value is None else f"{value:.0f} ms"


def _usd(value: float | None) -> str:
    return _NOT_DEFINED if value is None else f"${value:.4f}"


def _render_header(report: RunReport) -> list[str]:
    header = report.header
    runs = scored(report.results)
    errors = errored(report.results)
    return [
        "## Run header",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Run date | {header.run_date} |",
        f"| Git sha | {header.git_sha} |",
        f"| Suite | {header.suite} |",
        f"| Repeats | {header.repeats} |",
        f"| Evidence label | {header.evidence_label} |",
        f"| Sample size | {len(report.results)} cases; {len(runs)} scored; {len(errors)} errors |",
        f"| Policy | {header.policy_version} |",
        f"| Playbook | {header.playbook_version} |",
        f"| Rubric | {header.rubric_version} |",
        f"| Judge prompt | {header.judge_prompt_version} |",
        f"| Oracle | {header.oracle_version} |",
        f"| Laya | {header.laya_version or 'not recorded'} |",
        f"| Agent | {header.agent} |",
        f"| Agent model | {header.agent_model or 'none (no LLM calls)'} |",
        f"| Agent prompt | {header.agent_prompt_version or 'not applicable'} |",
        f"| Judge in the hub | {header.hub_judge} |",
        f"| Judge model | {header.judge_model or 'not configured'} |",
    ]


def _cost_cell(spend: Cost, header: RunHeader) -> str:
    """Priced cost, or the tokens when no price is on record (never a $0 that hides usage)."""
    tokens = f"{spend.prompt_tokens} prompt + {spend.completion_tokens} completion tokens"
    if (spend.prompt_tokens or spend.completion_tokens) and not header.llm_priced:
        return f"not priced ({tokens}; one pass, median of repeats)"
    cell = (
        f"{_usd(spend.per_attempt_usd)} / {_usd(spend.per_resolution_usd)} "
        f"(total {_usd(spend.total_usd)})"
    )
    if spend.prompt_tokens or spend.completion_tokens:
        cell += f"; {tokens}; one pass, median of repeats"
    return cell


def _render_headline(report: RunReport) -> list[str]:
    results = report.results
    label = report.header.evidence_label
    agreement = outcome_agreement(results)
    safe = safe_resolution(results)
    attempts = attempt_rate(results)
    contained = containment(results)
    escalation = escalation_quality(results)
    unsafe = unsafe_outcomes(results)
    lat = latency(results)
    spend = cost(results)
    lines = [
        "## Headline",
        "",
        "| Metric | Value | n | Label |",
        "|---|---|---|---|",
        (
            f"| Outcome agreement (vs oracle) | {_rate_cell(agreement)} | "
            f"{agreement.denominator} | {label} |"
        ),
        f"| Safe resolution | {_rate_cell(safe)} | {safe.denominator} | {label} |",
        f"| Attempt rate | {_rate_cell(attempts)} | {attempts.denominator} | {label} |",
        f"| Containment | {_rate_cell(contained)} | {contained.denominator} | {label} |",
        (
            "| Escalation quality | required "
            f"{escalation.required}, escalated {escalation.escalated}, missed "
            f"{len(escalation.missed_ids)}, unnecessary {len(escalation.unnecessary_ids)} | "
            f"{contained.denominator} | {label} |"
        ),
        (
            f"| Unsafe outcomes | {len(unsafe.fired_ids)}/{unsafe.denominator} fired | "
            f"{unsafe.denominator} | {label} |"
        ),
        (
            f"| Latency model p50/p95 | {_ms(lat.model_p50_ms)} / {_ms(lat.model_p95_ms)} | "
            f"{lat.n} | {label} |"
        ),
        (
            f"| Latency e2e p50/p95 | {_ms(lat.e2e_p50_ms)} / {_ms(lat.e2e_p95_ms)} | "
            f"{lat.n} | {label} |"
        ),
        (
            f"| Cost per attempt / per resolution | {_cost_cell(spend, report.header)} | "
            f"{spend.attempts} | {label} |"
        ),
    ]
    if escalation.missed_ids or escalation.unnecessary_ids:
        lines += [
            "",
            f"- Missed escalations: {', '.join(escalation.missed_ids) or 'none'}",
            f"- Unnecessary escalations: {', '.join(escalation.unnecessary_ids) or 'none'}",
        ]
    if unsafe.fired_ids:
        lines += ["", "Unsafe checks that fired:"]
        lines += [f"- `{check}`: {', '.join(ids)}" for check, ids in unsafe.by_check]
    return lines


def _render_oracle(report: RunReport) -> list[str]:
    agreement = outcome_agreement(report.results)
    lines = [
        "## Oracle agreement",
        "",
        f"- Oracle version {report.header.oracle_version}; outcome agreement "
        f"{_rate_cell(agreement)} over {agreement.denominator} scored cases "
        f"[{report.header.evidence_label}].",
    ]
    if report.gold_agreement is not None:
        lines.append(
            f"- Gold-subset agreement (oracle vs hand labels): "
            f"{_rate_cell(report.gold_agreement)} [measured]."
        )
    else:
        lines.append(f"- Gold-subset agreement: not run: {report.gold_blocker}.")
    return lines


def _render_baselines() -> list[str]:
    return [
        "## Baseline comparison",
        "",
        "- Human first-contact resolution on Transaccional calls: "
        f"{HUMAN_FIRST_CONTACT_RESOLUTION:.1%} [measured] (DESIGN.md, baselines). The target on "
        "calls is to match it with zero unsafe outcomes at lower time and cost.",
        "- Transactions-category complaints [measured] (reports/baseline/complaints.csv): "
        f"SLA breached {COMPLAINT_SLA_BREACHED_SHARE:.2%} of n={COMPLAINT_SLA_BREACHED_N}; "
        f"still open {COMPLAINT_STILL_OPEN_SHARE:.1%}.",
        "- Investigation savings: **projected only**. The data cannot link a call to its "
        "transaction, so no saving is stated as measured.",
    ]


def _render_language(report: RunReport) -> list[str]:
    slices = by_slice(report.results, lambda r: r.case.language)
    lines = ["## Language slices", "", "| Language | Outcome agreement | n |", "|---|---|---|"]
    for name, rate in slices.items():
        lines.append(f"| {name} | {_rate_cell(rate)} | {rate.denominator} |")
    lines += [
        "",
        "Dialect/language flip table: runs on whatever message pairs exist; today that is the "
        "ES set alone, so the PT column is not run: T-203 (the Portuguese set). The "
        "counterfactual suite stays Tier 1 (T-405).",
    ]
    return lines


def _render_adversarial(report: RunReport) -> list[str]:
    adversarial = tuple(r for r in report.results if r.case.adversarial is not None)
    lines = ["## Adversarial results", ""]
    if not adversarial:
        lines.append("No adversarial cases in this run.")
        return lines
    slices = by_slice(adversarial, lambda r: r.case.adversarial)
    unsafe = unsafe_outcomes(adversarial)
    lines += ["| Category | Outcome agreement | n |", "|---|---|---|"]
    for name, rate in slices.items():
        lines.append(f"| {name} | {_rate_cell(rate)} | {rate.denominator} |")
    lines += [
        "",
        f"Unsafe outcomes on the adversarial slice: {len(unsafe.fired_ids)} of "
        f"{unsafe.denominator} cases fired [{report.header.evidence_label}].",
    ]
    if unsafe.fired_ids:
        lines += [f"- `{check}`: {', '.join(ids)}" for check, ids in unsafe.by_check]
    return lines


def _render_ablation(report: RunReport) -> list[str]:
    ablation = report.ablation
    lines = ["## Ablation (bare LLM, no harness)", ""]
    if not ablation.ran:
        lines.append(f"not run: {ablation.blocker}")
        return lines
    calvino_unsafe = unsafe_outcomes(report.results)
    calvino_cell = f"{len(calvino_unsafe.fired_ids)}/{calvino_unsafe.denominator}"
    lines += [
        f"Bare prompt version {ablation.prompt_version}; model {ablation.model}; "
        f"{len(ablation.answers)} answers.",
        "",
        "| | Unsafe fired | n |",
        "|---|---|---|",
        (
            f"| Bare LLM | {len(ablation.unsafe.fired_ids)}/{ablation.unsafe.denominator} | "
            f"{ablation.unsafe.denominator} |"
        ),
        f"| Calvino (this run) | {calvino_cell} | {calvino_unsafe.denominator} |",
    ]
    if ablation.unsafe.fired_ids:
        lines += ["", "Bare-model unsafe checks that fired:"]
        lines += [f"- `{check}`: {', '.join(ids)}" for check, ids in ablation.unsafe.by_check]
    return lines


def _render_judge(report: RunReport) -> list[str]:
    judge = report.judge
    lines = ["## Judge validation", ""]
    if not judge.ran:
        lines.append(f"not run: {judge.blocker}")
        return lines
    false_pass = ", ".join(judge.false_pass_ids) or "none"
    false_fail = ", ".join(judge.false_fail_ids) or "none"
    lines += [
        f"Judge {judge.judge_model or 'unnamed'} vs agent {judge.agent_model or 'unnamed'}; "
        f"rubric {judge.rubric_ref}; {judge.judged} (case, criterion) pairs judged.",
        "",
        f"- Agreement: {_rate_cell(judge.agreement)}",
        f"- False passes (judge passed a labelled fail): {false_pass}",
        f"- False fails (judge failed a labelled pass): {false_fail}",
        f"- Cost per criterion: {_usd(judge.cost_per_criterion_usd)}"
        + ("" if judge.cost_usd is not None else " (not metered)"),
    ]
    if judge.missing_reply_ids:
        missing = ", ".join(judge.missing_reply_ids)
        lines.append(f"- Labelled cases without a captured reply: {missing}")
    return lines


def _render_determinism(report: RunReport) -> list[str]:
    lines = ["## Repeated-run variability", ""]
    if report.determinism:
        lines += [
            f"{len(report.determinism)} differences across {report.header.repeats} repeats "
            "(a difference is a finding, not noise):",
        ]
        lines += [f"- {finding}" for finding in report.determinism]
    else:
        lines.append(
            f"No differences across {report.header.repeats} repeats: every verdict replayed "
            f"identically [{report.header.evidence_label}]. Generative components, when live, "
            "are stated here per component."
        )
    return lines


def _render_errors(report: RunReport) -> list[str]:
    errors = errored(report.results)
    lines = ["## Error analysis", ""]
    if not errors:
        lines.append("No errored turns in this run.")
        return lines
    groups: dict[str, list[str]] = {}
    for result in errors:
        message = result.error or "turn produced no outcome"
        groups.setdefault(message, []).append(result.case.id)
    lines.append(f"{len(errors)} errored turns, grouped by failure (fail-closed counting):")
    for message, ids in sorted(groups.items(), key=lambda item: -len(item[1])):
        lines.append(f"- {message}: {', '.join(ids)}")
    return lines


def _render_limitations(report: RunReport) -> list[str]:
    return [
        "## Limitations",
        "",
        f"- The run evaluates the system as built when it ran: agent {report.header.agent}, "
        f"judge in the hub {report.header.hub_judge}, Spanish only, until the message set "
        "(T-106) and the Portuguese set (T-203) land as data and configuration.",
        "- The hub's Laya-tier checks are still the fake that passes every criterion they own; "
        "only the code checks and the judge constrain a reply.",
        "- Unsafe checks are conservative v1 observations: a check that cannot see a violation "
        "stays silent, so false negatives are possible (false positives are not). The "
        "reply-wording unsafe (a promise the policy does not allow) is Tier 1.",
        "- Laya is self-hosted: its cost is CPU time, reported as latency and $0 in the cost "
        "table.",
        "- Baselines are category-level: the data cannot link a call to its transaction, so "
        "investigation savings stay projected.",
        f"- Evidence label for this run: {report.header.evidence_label}; sample size "
        f"{len(report.results)} cases over {report.header.repeats} repeats.",
    ]


def render_report(report: RunReport) -> str:
    """The human report: every fixed section, in order, with n and labels."""
    sections: Iterable[Sequence[str]] = (
        [f"# Calvino evaluation report: {report.header.suite} ({report.header.run_date})", ""],
        _render_header(report),
        _render_headline(report),
        _render_oracle(report),
        _render_baselines(),
        _render_language(report),
        _render_adversarial(report),
        _render_ablation(report),
        _render_judge(report),
        _render_determinism(report),
        _render_errors(report),
        _render_limitations(report),
    )
    body: list[str] = []
    for section in sections:
        body += [*section, ""]
    return "\n".join(body).rstrip() + "\n"


def _case_object(result: CaseResult) -> dict:
    """One case for the machine results: the CaseResult fields, JSON-safe."""
    case = result.case
    return {
        "case_id": case.id,
        "persona": case.persona,
        "language": case.language,
        "adversarial": case.adversarial,
        "edge_case": case.edge_case,
        "expected": str(case.expected),
        "outcome": str(result.outcome) if result.outcome is not None else None,
        "actual_route": result.actual_route,
        "parked": list(result.parked),
        "tool_calls": list(result.tool_calls),
        "unsafe": list(result.unsafe),
        "latency_model_ms": result.latency_model_ms,
        "latency_e2e_ms": result.latency_e2e_ms,
        "cost_usd": result.cost_usd,
        "llm_prompt_tokens": result.llm_prompt_tokens,
        "llm_completion_tokens": result.llm_completion_tokens,
        "error": result.error,
        "trace": [
            {"stage": step.stage, "rule_id": step.rule_id, "verdict": step.verdict}
            for step in result.trace
        ],
        "decision_records": list(result.decision_records),
    }


def results_json(report: RunReport) -> dict:
    """The machine results: a run header plus one object per case.

    A compact metrics block is included so a reader does not have to
    recompute the headline from the cases; every rate keeps its counts.
    """
    header = report.header
    results = report.results
    unsafe = unsafe_outcomes(results)
    spend = cost(results)
    return {
        "header": {
            "run_date": header.run_date,
            "git_sha": header.git_sha,
            "suite": header.suite,
            "repeats": header.repeats,
            "evidence_label": header.evidence_label,
            "policy_version": header.policy_version,
            "playbook_version": header.playbook_version,
            "rubric_version": header.rubric_version,
            "judge_prompt_version": header.judge_prompt_version,
            "oracle_version": header.oracle_version,
            "laya_version": header.laya_version,
            "agent_model": header.agent_model,
            "judge_model": header.judge_model,
            "agent": header.agent,
            "agent_prompt_version": header.agent_prompt_version,
            "hub_judge": header.hub_judge,
            "llm_priced": header.llm_priced,
        },
        "metrics": {
            "outcome_agreement": asdict(outcome_agreement(results)),
            "safe_resolution": asdict(safe_resolution(results)),
            "attempt_rate": asdict(attempt_rate(results)),
            "containment": asdict(containment(results)),
            "escalation_quality": asdict(escalation_quality(results)),
            "unsafe_outcomes": asdict(unsafe),
            "latency": asdict(latency(results)),
            "cost": asdict(spend),
        },
        "determinism_findings": list(report.determinism),
        "judge_validation": asdict(report.judge),
        "ablation": asdict(report.ablation),
        "cases": [_case_object(result) for result in results],
    }


def results_json_text(report: RunReport) -> str:
    """The machine results as sorted-key JSON text (the committed .json)."""
    return json.dumps(results_json(report), indent=2, sort_keys=True, default=str) + "\n"
