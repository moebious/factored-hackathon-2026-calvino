"""Tests for the evaluation report writer (TSD-013).

The writer's contract: every fixed section present in the fixed order,
every rate line carrying its counts and an evidence label, undefined
rates rendered "not defined" (never a number), gated sections rendering
"not run: <blocker>" when their prerequisite is missing, and the machine
results mirroring the same data. Pure rendering from synthetic inputs:
no hub, no models, no network.
"""

from __future__ import annotations

import json
from dataclasses import replace

from calvino.evaluation.ablation import BARE_PROMPT_VERSION, Ablation, BareAnswer
from calvino.evaluation.cases import EvalCase
from calvino.evaluation.judge_validation import JudgeConfusion
from calvino.evaluation.metrics import Rate, Unsafe
from calvino.evaluation.oracle import ExpectedOutcome, OracleFacts
from calvino.evaluation.report import (
    GOLD_BLOCKER,
    SECTIONS,
    RunHeader,
    RunReport,
    render_report,
    results_json,
    results_json_text,
)
from calvino.evaluation.runner import CaseResult

KEYS_JUDGE_BLOCKER = "CALVINO_JUDGE_API_KEY and CALVINO_JUDGE_MODEL absent"
KEYS_AGENT_BLOCKER = "CALVINO_LLM_API_KEY and CALVINO_LLM_MODEL absent"


def header(**overrides: object) -> RunHeader:
    values: dict = {
        "run_date": "2026-10-04",
        "git_sha": "abc1234",
        "suite": "tier0",
        "repeats": 3,
        "evidence_label": "offline",
        "policy_version": "v2",
        "playbook_version": "v1",
        "rubric_version": "customer-answer@1",
        "judge_prompt_version": 1,
        "oracle_version": "1",
        "laya_version": None,
        "agent_model": None,
        "judge_model": None,
    }
    values.update(overrides)
    return RunHeader(**values)


def make_case(
    case_id: str,
    *,
    expected: ExpectedOutcome = ExpectedOutcome.EXPLAIN,
    language: str = "es",
    adversarial: str | None = None,
) -> EvalCase:
    return EvalCase(
        id=case_id,
        persona="lucia",
        language=language,
        message="mensaje",
        seed_record=None,
        adversarial=adversarial,
        edge_case=None,
        facts=OracleFacts(
            intent="explain",
            ambiguous=False,
            status=None,
            owner=True,
            amount_band="under_gate",
            fraud_flag=False,
            in_scope=True,
        ),
        must_not=(),
        resume_script=(),
        expected=expected,
    )


def make_result(
    case: EvalCase,
    outcome: ExpectedOutcome | None = None,
    *,
    error: str | None = None,
) -> CaseResult:
    # Like the runner: an errored turn carries no outcome unless one is given.
    if outcome is None and error is None:
        outcome = case.expected
    return CaseResult(
        case=case,
        outcome=outcome,
        actual_route="agents",
        parked=(),
        tool_calls=(),
        unsafe=(),
        latency_model_ms=10.0,
        latency_e2e_ms=20.0,
        cost_usd=0.0,
        trace=(),
        decision_records=(),
        error=error,
    )


def judge_not_run() -> JudgeConfusion:
    return JudgeConfusion(
        ran=False,
        blocker=KEYS_JUDGE_BLOCKER,
        judge_model=None,
        agent_model=None,
        rubric_ref="customer-answer@1",
        judged=0,
        false_pass_ids=(),
        false_fail_ids=(),
        agreement=Rate(0, 0),
        missing_reply_ids=(),
        cost_usd=None,
        cost_per_criterion_usd=None,
    )


def ablation_not_run() -> Ablation:
    return Ablation(
        ran=False,
        blocker=KEYS_AGENT_BLOCKER,
        model=None,
        prompt_version=BARE_PROMPT_VERSION,
        answers=(),
        unsafe=Unsafe(denominator=0, fired_ids=(), by_check=()),
    )


def make_report(
    results: tuple[CaseResult, ...] = (),
    *,
    determinism: tuple[str, ...] = (),
    judge: JudgeConfusion | None = None,
    ablation: Ablation | None = None,
    gold_agreement: Rate | None = None,
    gold_blocker: str | None = GOLD_BLOCKER,
) -> RunReport:
    return RunReport(
        header=header(),
        results=results,
        determinism=determinism,
        judge=judge or judge_not_run(),
        ablation=ablation or ablation_not_run(),
        gold_agreement=gold_agreement,
        gold_blocker=gold_blocker,
    )


def sample_results() -> tuple[CaseResult, ...]:
    return (
        make_result(make_case("ORC-001")),
        make_result(make_case("ORC-002"), ExpectedOutcome.CLARIFY),  # a mismatch
        make_result(make_case("ADV-001", adversarial="prompt injection")),
        make_result(make_case("ADV-002", adversarial="prompt injection"), error="boom"),
    )


def test_every_fixed_section_present_in_order() -> None:
    rendered = render_report(make_report(sample_results()))
    positions = [rendered.index(f"## {name}") for name in SECTIONS]
    assert positions == sorted(positions)


def test_headline_rates_carry_counts_and_the_evidence_label() -> None:
    rendered = render_report(make_report(sample_results()))
    # 2 of 3 scored results agree with the oracle; the error is excluded.
    assert "| Outcome agreement (vs oracle) | 2/3 (66.7%) | 3 | offline |" in rendered
    assert "| Containment | 3/3 (100.0%) | 3 | offline |" in rendered


def test_empty_run_renders_not_defined_never_a_number() -> None:
    rendered = render_report(make_report(()))
    assert "not defined (n=0)" in rendered
    assert "0.0%" not in rendered


def test_gated_sections_render_their_blockers() -> None:
    rendered = render_report(make_report(sample_results()))
    assert f"not run: {KEYS_JUDGE_BLOCKER}" in rendered
    assert f"not run: {KEYS_AGENT_BLOCKER}" in rendered


def test_gold_subset_blocker_and_agreement() -> None:
    blocked = render_report(make_report(sample_results()))
    assert f"not run: {GOLD_BLOCKER}" in blocked
    agreed = render_report(make_report(sample_results(), gold_agreement=Rate(9, 10)))
    assert "Gold-subset agreement (oracle vs hand labels): 9/10 (90.0%) [measured]" in agreed


def test_baselines_are_quoted_with_their_labels() -> None:
    rendered = render_report(make_report(sample_results()))
    assert "91.5% [measured]" in rendered
    assert "SLA breached 20.17% of n=13580" in rendered
    assert "**projected only**" in rendered


def test_language_slices_and_the_pt_flip_blocker() -> None:
    results = (*sample_results(), make_result(make_case("PT-1", language="pt")))
    rendered = render_report(make_report(results))
    assert "| es |" in rendered
    assert "| pt |" in rendered
    assert "not run: T-203" in rendered


def test_adversarial_section_groups_by_category() -> None:
    rendered = render_report(make_report(sample_results()))
    assert "| prompt injection |" in rendered
    # ADV-002 errored, so the scored adversarial denominator is 1, not 2.
    assert "Unsafe outcomes on the adversarial slice: 0 of 1 cases fired" in rendered


def test_judge_section_renders_the_confusion_when_it_ran() -> None:
    judge = JudgeConfusion(
        ran=True,
        blocker=None,
        judge_model="deepseek-chat",
        agent_model="Qwen3.8-27B",
        rubric_ref="customer-answer@1",
        judged=4,
        false_pass_ids=("ORC-001/grounded",),
        false_fail_ids=(),
        agreement=Rate(3, 4),
        missing_reply_ids=(),
        cost_usd=0.08,
        cost_per_criterion_usd=0.02,
    )
    rendered = render_report(make_report(sample_results(), judge=judge))
    assert "not run:" not in rendered.split("## Judge validation")[1].split("##")[0]
    assert "Agreement: 3/4 (75.0%)" in rendered
    assert "ORC-001/grounded" in rendered
    assert "$0.0200" in rendered


def test_ablation_section_renders_side_by_side_when_it_ran() -> None:
    ablation = Ablation(
        ran=True,
        blocker=None,
        model="Qwen3.8-27B",
        prompt_version=BARE_PROMPT_VERSION,
        answers=(
            BareAnswer(
                case_id="ADV-001",
                text="listo",
                model="Qwen3.8-27B",
                prompt_tokens=10,
                completion_tokens=5,
                latency_ms=100.0,
            ),
        ),
        unsafe=Unsafe(
            denominator=1,
            fired_ids=("ADV-001",),
            by_check=(("acted_without_approval", ("ADV-001",)),),
        ),
    )
    rendered = render_report(make_report(sample_results(), ablation=ablation))
    section = rendered.split("## Ablation")[1].split("##")[0]
    assert "| Bare LLM | 1/1 | 1 |" in section
    assert "| Calvino (this run) |" in section
    assert "`acted_without_approval`: ADV-001" in section


def test_determinism_findings_are_listed_not_averaged() -> None:
    quiet = render_report(make_report(sample_results()))
    assert "No differences across 3 repeats" in quiet
    loud = render_report(make_report(sample_results(), determinism=("ORC-001: repeat 2 differs",)))
    assert "- ORC-001: repeat 2 differs" in loud


def test_errors_are_grouped_by_failure_message() -> None:
    results = (
        make_result(make_case("A"), error="boom"),
        make_result(make_case("B"), error="boom"),
        make_result(make_case("C"), error="bang"),
    )
    rendered = render_report(make_report(results))
    assert "- boom: A, B" in rendered
    assert "- bang: C" in rendered


def test_results_json_mirrors_the_run() -> None:
    report = make_report(sample_results(), determinism=("ORC-001: repeat 2 differs",))
    payload = results_json(report)
    assert payload["header"]["git_sha"] == "abc1234"
    assert payload["header"]["suite"] == "tier0"
    assert payload["metrics"]["outcome_agreement"] == {"numerator": 2, "denominator": 3}
    assert payload["determinism_findings"] == ["ORC-001: repeat 2 differs"]
    assert payload["judge_validation"]["ran"] is False
    assert payload["ablation"]["ran"] is False
    assert [case["case_id"] for case in payload["cases"]] == [
        "ORC-001",
        "ORC-002",
        "ADV-001",
        "ADV-002",
    ]
    errored_case = payload["cases"][3]
    assert errored_case["outcome"] is None
    assert errored_case["error"] == "boom"


def test_results_json_text_is_valid_json() -> None:
    text = results_json_text(make_report(sample_results()))
    assert json.loads(text)["header"]["run_date"] == "2026-10-04"


def llm_result(case_id: str, prompt: int, completion: int, cost_usd: float = 0.0) -> CaseResult:
    return replace(
        make_result(make_case(case_id)),
        llm_prompt_tokens=prompt,
        llm_completion_tokens=completion,
        cost_usd=cost_usd,
    )


def test_the_header_names_the_components_that_answered() -> None:
    template = render_report(make_report())
    assert "| Agent | TemplateAgent |" in template
    assert "| Judge in the hub | none: judged criteria are not run |" in template
    live = render_report(
        replace(
            make_report(),
            header=header(
                agent="LlmAgent",
                agent_model="qwen-test",
                agent_prompt_version="v1",
                hub_judge="OpenAiJudge (judge-test)",
            ),
        )
    )
    assert "| Agent | LlmAgent |" in live
    assert "| Agent model | qwen-test |" in live and "| Agent prompt | v1 |" in live
    assert "| Judge in the hub | OpenAiJudge (judge-test) |" in live


def test_the_header_versions_the_unsafe_checks() -> None:
    text = render_report(make_report())
    assert "| Unsafe checks | v2: outcomes plus reply wording |" in text
    assert results_json(make_report())["header"]["unsafe_checks"].startswith("v2")


def test_unpriced_tokens_are_reported_not_shown_as_zero_cost() -> None:
    results = (llm_result("ORC-001", 1000, 200), llm_result("ORC-002", 500, 100))
    unpriced = render_report(replace(make_report(results), header=header(llm_priced=False)))
    assert "not priced (1500 prompt + 300 completion tokens" in unpriced
    assert "$0.0000 / $0.0000" not in unpriced


def test_priced_cost_shows_money_and_tokens() -> None:
    results = (llm_result("ORC-001", 1000, 200, cost_usd=0.5),)
    priced = render_report(make_report(results))
    assert "$0.5000" in priced and "1000 prompt + 200 completion tokens" in priced


def test_results_json_carries_tokens_and_the_answering_components() -> None:
    payload = results_json(
        replace(
            make_report((llm_result("ORC-001", 1000, 200),)),
            header=header(agent="LlmAgent", agent_prompt_version="v1"),
        )
    )
    assert payload["header"]["agent"] == "LlmAgent"
    assert payload["header"]["agent_prompt_version"] == "v1"
    assert payload["cases"][0]["llm_prompt_tokens"] == 1000
    assert payload["metrics"]["cost"]["completion_tokens"] == 200
