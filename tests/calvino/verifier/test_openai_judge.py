"""Tests for the real judge over a provider (TSD-009 / TSD-004).

Everything runs offline: the client is the fake from the LLM tests, and the one test that drives
the cascade uses it too.
"""

from __future__ import annotations

import json

import pytest

from calvino.llm.errors import LlmRateLimited
from calvino.verifier.cascade import Verifier
from calvino.verifier.evidence import Evidence
from calvino.verifier.judge import JUDGE_PROMPT_VERSION, MockJudge, OpenAiJudge
from calvino.verifier.rubric import CheckerKind, Criterion, Severity


def criteria(*ids: str) -> list[Criterion]:
    # The checklist is split out of the criterion text, so the text carries both parts.
    return [
        Criterion(
            id=cid,
            text=f"criterion {cid}; item for {cid}",
            checker=CheckerKind.JUDGE,
            severity=Severity.BLOCKING,
        )
        for cid in ids
    ]


def evidence() -> Evidence:
    return Evidence(customer_language="es")


def verdict_json(*ids: str, passed: bool = True) -> str:
    return json.dumps(
        {"verdicts": [{"criterion_id": cid, "passed": passed, "reason": "checked"} for cid in ids]}
    )


def judge_replying(text: str, factory, *, seed: int | None = None, **kwargs):
    fake = factory({"verifier-judge": text}, **kwargs)
    return OpenAiJudge(fake, seed=seed), fake


def test_one_call_decides_every_criterion(fake_chat_client_factory):
    judge, fake = judge_replying(verdict_json("c1", "c2", "c3"), fake_chat_client_factory)
    verdicts = judge.judge_batch("Su pago está pendiente.", evidence(), criteria("c1", "c2", "c3"))

    assert [v.criterion_id for v in verdicts] == ["c1", "c2", "c3"]
    assert all(v.passed for v in verdicts)
    assert len(fake.requests) == 1, "decision 14 requires one batched call"


def test_the_request_carries_no_sampling_a_seed_and_low_reasoning(fake_chat_client_factory):
    judge, fake = judge_replying(verdict_json("c1"), fake_chat_client_factory, seed=99)
    judge.judge_batch("hola", evidence(), criteria("c1"))

    sent = fake.requests[0]
    assert sent.role.value == "judge"
    assert sent.temperature == 0.0, "a verdict is a decision, not prose"
    assert sent.seed == 99
    assert sent.reasoning_effort.value == "low"
    assert sent.purpose == "verifier-judge"


def test_the_prompt_is_the_versioned_one_and_the_model_is_reported(fake_chat_client_factory):
    judge, fake = judge_replying(
        verdict_json("c1"), fake_chat_client_factory, model="deepseek/deepseek-v4-pro-0813"
    )
    judge.judge_batch("Su pago está pendiente.", evidence(), criteria("c1"))

    prompt = fake.requests[0].messages[0].content
    assert "Responde" not in prompt  # the template is English; the check is on its structure
    assert "criterion c1" in prompt
    assert "item for c1" in prompt
    assert judge.prompt_version == JUDGE_PROMPT_VERSION
    assert judge.last_model == "deepseek/deepseek-v4-pro-0813"


def test_an_unreadable_reply_fails_every_criterion_rather_than_raising(fake_chat_client_factory):
    judge, _ = judge_replying("I think it looks fine, honestly.", fake_chat_client_factory)
    verdicts = judge.judge_batch("hola", evidence(), criteria("c1", "c2"))

    assert [v.passed for v in verdicts] == [False, False]
    assert "could not be read" in verdicts[0].reason


def test_a_criterion_the_reply_skips_fails_on_its_own(fake_chat_client_factory):
    judge, _ = judge_replying(verdict_json("c1"), fake_chat_client_factory)
    verdicts = judge.judge_batch("hola", evidence(), criteria("c1", "c2"))

    assert verdicts[0].passed is True
    assert verdicts[1].passed is False
    assert "no clear verdict" in verdicts[1].reason


def test_no_criteria_means_no_call(fake_chat_client_factory):
    judge, fake = judge_replying("unused", fake_chat_client_factory)
    assert judge.judge_batch("hola", evidence(), []) == []
    assert fake.requests == []


def test_the_judge_is_swappable_for_the_scripted_one():
    """The protocol is the seam: MockJudge still stands in everywhere."""
    mock = MockJudge({"c1": (False, "scripted")})
    verdicts = mock.judge_batch("hola", evidence(), criteria("c1", "c2"))
    assert [(v.criterion_id, v.passed) for v in verdicts] == [("c1", False), ("c2", True)]


def test_the_adapter_does_not_swallow_a_provider_failure(fake_chat_client_factory):
    """Fail-closed is the cascade's job (TSD-004); the adapter must not invent verdicts."""
    fake = fake_chat_client_factory()

    def boom(request):
        raise LlmRateLimited("rate limit")

    fake.complete = boom  # type: ignore[method-assign]

    with pytest.raises(LlmRateLimited):
        OpenAiJudge(fake).judge_batch("hola", evidence(), criteria("c1"))


def test_the_cascade_turns_a_provider_failure_into_failed_criteria(fake_chat_client_factory):
    fake = fake_chat_client_factory()

    def boom(request):
        raise LlmRateLimited("rate limit")

    fake.complete = boom  # type: ignore[method-assign]
    verifier = Verifier(judge=OpenAiJudge(fake))
    result = verifier.verify("Su pago está pendiente.", evidence())

    judge_verdicts = [v for v in result.verdicts if v.checker.value == "judge"]
    assert judge_verdicts, "the rubric has judge criteria, so the tier ran"
    assert not any(v.passed for v in judge_verdicts)
    assert any("LlmRateLimited" in v.reason for v in judge_verdicts)


def test_reading_the_cascade_does_not_import_the_http_client():
    """The external boundary stays explicit: no HTTP stack until a client is built."""
    import subprocess
    import sys

    probe = "import sys, calvino.verifier; print('httpx' in sys.modules)"
    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "False", result.stdout
