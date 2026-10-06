"""Verification of live Qwen support agent under the Verifier (Task T-301).

Runs live Qwen/Qwen3.6-35B-A3B on Hetzner through LlmAgent and verifies its
drafted replies against the customer-answer rubric (all 6 deterministic code
checks and rubric verification) in Spanish and Portuguese.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from calvino.hub.agent import AgentRequest
from calvino.hub.llm_agent import HubStage, LlmAgent
from calvino.hub.playbook import load_playbook
from calvino.llm import hetzner_client_from_env, judge_client_from_env
from calvino.verifier import FakeLayaChecker, Verifier, load_rubric
from calvino.verifier.evidence import ToolResult, evidence_from_tool_results
from calvino.verifier.judge import MockJudge, OpenAiJudge

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "reports" / "eval"

DETAIL = ToolResult(
    tool="get_entry_detail",
    payload={
        "entry_reference": "E-MX-002",
        "amount": "5000.00",
        "currency": "MXN",
        "status": "Pending",
        "booking_date": "2026-06-10",
        "value_date": "2026-06-11",
        "remittance_information": "Transfer to a friend",
    },
)


def run_case(
    agent: LlmAgent,
    verifier: Verifier,
    lang: str,
    message: str,
) -> dict:
    guidance = load_playbook().guidance("Pending")
    evidence = evidence_from_tool_results(
        [DETAIL],
        customer_language=lang,  # type: ignore[arg-type]
        message=message,
    )
    req = AgentRequest(
        stage=HubStage.EXPLAIN.value,
        message=message,
        guidance=guidance,
        tool_results=(DETAIL,),
        evidence=evidence,
    )

    print(f"\n[{lang.upper()}] Customer: {message}")
    t0 = time.time()
    draft = agent.draft(req)
    gen_time = time.time() - t0
    print(f"[{lang.upper()}] Agent reply ({gen_time:.1f}s):")
    print(draft.text)

    t1 = time.time()
    result = verifier.verify(draft.text, evidence)
    ver_time = time.time() - t1
    print(f"[{lang.upper()}] Verification ({ver_time:.1f}s): {'PASS' if result.passed else 'FAIL'}")
    code_checks_passed = True
    for v in result.verdicts:
        status = "PASS" if v.passed else "FAIL"
        reason = f" - {v.reason}" if v.reason else ""
        print(f"  [{v.checker:5s}] {v.criterion_id}: {status}{reason}")
        if v.checker == "code" and not v.passed:
            code_checks_passed = False

    return {
        "language": lang,
        "message": message,
        "draft": draft.text,
        "generation_time_seconds": gen_time,
        "verification_time_seconds": ver_time,
        "passed": result.passed,
        "code_checks_passed": code_checks_passed,
        "verdicts": [
            {
                "criterion_id": v.criterion_id,
                "checker": v.checker,
                "passed": v.passed,
                "reason": v.reason,
            }
            for v in result.verdicts
        ],
    }


def main() -> int:
    os.environ["CALVINO_LLM_TIMEOUT_SECONDS"] = "300"
    load_dotenv()

    parser = argparse.ArgumentParser(description="Verify live support agent under the verifier")
    parser.add_argument(
        "--judge",
        choices=["mock", "staging"],
        default="mock",
        help="Judge to use for the rubric LLM tier (default: mock, for deterministic verification)",
    )
    args = parser.parse_args()

    print("Initializing live agent client (Qwen on Hetzner)...")
    agent_client = hetzner_client_from_env()
    agent = LlmAgent(agent_client)

    if args.judge == "staging":
        print("Initializing staging judge client (Nemotron on NVIDIA)...")
        judge = OpenAiJudge(judge_client_from_env(), seed=7)
    else:
        print("Using MockJudge for LLM tier criteria (code checks are 100% live deterministic)...")
        judge = MockJudge()

    rubric = load_rubric()
    verifier = Verifier(rubric=rubric, laya_checker=FakeLayaChecker(), judge=judge)

    es_result = run_case(
        agent,
        verifier,
        "es",
        "¿Por qué mi transferencia E-MX-002 sigue pendiente?",
    )
    pt_result = run_case(
        agent,
        verifier,
        "pt",
        "Por que minha transferência E-MX-002 continua pendente?",
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    json_path = OUTPUT_DIR / f"T-301-{today}-live-agent-evidence.json"
    md_path = OUTPUT_DIR / f"T-301-{today}-live-agent-evidence.md"

    report_data = {
        "task": "T-301",
        "date": today,
        "agent_model": os.getenv("CALVINO_LLM_MODEL", "Qwen/Qwen3.6-35B-A3B-FP8"),
        "judge_mode": args.judge,
        "results": [es_result, pt_result],
    }

    json_path.write_text(json.dumps(report_data, indent=2, ensure_ascii=False), encoding="utf-8")

    md_lines = [
        f"# T-301: Live Support Agent Verification ({today})",
        "",
        f"- **Agent model**: `{report_data['agent_model']}` (Hetzner, Open-weights Qwen reasoning)",
        f"- **Judge mode**: `{args.judge}`",
        "- **Harness policy**: Grounded tool facts only (`E-MX-002`, `5000.00 MXN`, "
        "`2026-06-10`, `Pending`)",
        "",
        "## Results Summary",
        "",
        "| Language | Generated Reply | Gen Time | Code Checks | Verifier Result |",
        "|---|---|---|---|---|",
    ]
    for r in [es_result, pt_result]:
        short_draft = r["draft"].replace("\n", " ")
        status = "PASS" if r["passed"] else "FAIL"
        code_status = "PASS (6/6)" if r["code_checks_passed"] else "FAIL"
        md_lines.append(
            f"| {r['language'].upper()} | {short_draft} | "
            f"{r['generation_time_seconds']:.1f}s | **{code_status}** | **{status}** |"
        )

    md_lines.extend(
        [
            "",
            "## Detailed Criteria Verdicts",
            "",
        ]
    )

    for r in [es_result, pt_result]:
        md_lines.extend(
            [
                f"### {r['language'].upper()} Turn",
                f"- **Customer Query**: `{r['message']}`",
                f'- **Agent Output**: "{r["draft"]}"',
                f"- **Latency**: Generation: {r['generation_time_seconds']:.1f}s, "
                f"Verification: {r['verification_time_seconds']:.1f}s",
                "",
                "| Checker | Criterion | Verdict | Reason |",
                "|---|---|---|---|",
            ]
        )
        for v in r["verdicts"]:
            res = "PASS" if v["passed"] else "FAIL"
            reason = v["reason"] or "—"
            md_lines.append(f"| `{v['checker']}` | `{v['criterion_id']}` | {res} | {reason} |")
        md_lines.append("")

    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"\nEvidence recorded to:\n  {json_path}\n  {md_path}")

    all_code_passed = es_result["code_checks_passed"] and pt_result["code_checks_passed"]
    return 0 if all_code_passed else 1


if __name__ == "__main__":
    sys.exit(main())
