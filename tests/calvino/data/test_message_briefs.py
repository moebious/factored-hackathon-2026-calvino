"""Tests for the brief builder (TSD-019, T-106): offline, synthetic seeds."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import generate_message_set as gen

from calvino.data.message_briefs import build_plain_briefs, build_rewording_briefs
from calvino.data.message_set import BRIEF_DEFAULTS, SeedRow


def seed(key, kind, country="MX", split="train", parent=None) -> SeedRow:
    return SeedRow.model_validate(
        {
            "seed_key": key,
            "split": split,
            "prompt_id": "train-v1",
            "kind": kind,
            "parent_seed_key": parent,
            "customer_hash": key.ljust(16, "0"),
            "country_variant": country,
            "record_facts": {"kind": kind},
            "event_date": "2024-03-10",
            "policy_version": "v2",
        }
    )


def full_pool(split="train", per_kind=60):
    kinds = ("problem_transaction", "clean_transaction", "other_customer", "complaint", "no_record")
    return [
        seed(f"v1-{country}-{kind}-{i}", kind, country, split)
        for country in ("MX", "CO", "AR")
        for kind in kinds
        for i in range(per_kind)
    ]


def test_train_composition_is_200_per_variant():
    report = build_plain_briefs("train", full_pool(per_kind=80))
    assert report.shortfalls == []
    assert len(report.briefs) == 600
    by_intent = {}
    for brief in report.briefs:
        by_intent[brief["intent"]] = by_intent.get(brief["intent"], 0) + 1
    assert by_intent["explain"] == 75 and by_intent["manipulation"] == 60
    assert by_intent["dispute"] == 30 and by_intent["case_status"] == 75


def test_calibration_is_80_per_variant_and_intents_are_known():
    report = build_plain_briefs("calibration", full_pool("calibration"))
    assert len(report.briefs) == 240
    assert all(brief["intent"] in BRIEF_DEFAULTS for brief in report.briefs)


def test_builder_is_deterministic_and_order_independent():
    pool = full_pool()
    first = build_plain_briefs("train", pool).briefs
    second = build_plain_briefs("train", list(reversed(pool))).briefs
    assert sorted(first, key=lambda b: b["seed_key"]) == sorted(second, key=lambda b: b["seed_key"])


def test_thin_pool_reports_shortfalls_instead_of_filling_with_other_kinds():
    pool = [seed(f"v1-x{i}", "clean_transaction") for i in range(5)]
    report = build_plain_briefs("train", pool)
    assert any("case_status" in s for s in report.shortfalls)
    assert not any(b["intent"] == "case_status" for b in report.briefs)
    assert len(report.briefs) == 5


def test_rewordings_inherit_parent_intent_and_adversarial_kinds():
    parents = {f"p{i}": {"seed_key": f"p{i}", "intent": "cancel"} for i in range(40)}
    seeds = [seed(f"v1-r{i}", "rewording", split="test", parent=f"p{i}") for i in range(40)]
    report = build_rewording_briefs(seeds, parents, {"p0": "hola"})
    assert report.shortfalls == []
    kinds = [b["adversarial_kind"] for b in report.briefs]
    assert kinds.count("injection") == 10 and kinds.count("edge") == 12
    for brief in report.briefs:
        if brief["adversarial_kind"] == "injection":
            assert brief["intent"] == "manipulation"
        elif brief.get("edge_kind") in ("empty", "emoji_only", "garbled"):
            assert brief["intent"] == "none"
        else:
            assert brief["intent"] == "cancel"
    assert sum("parent_message" in b for b in report.briefs) == 1


def test_dry_run_without_briefs_builds_them_and_does_not_crash(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(gen, "is_git_ignored", lambda path: True)
    registry = tmp_path / "seeds.jsonl"
    registry.write_text(
        "\n".join(s.model_dump_json() for s in full_pool(per_kind=2)) + "\n", encoding="utf-8"
    )
    prompt = tmp_path / "p.md"
    prompt.write_text("draft", encoding="utf-8")
    out = tmp_path / "briefs.jsonl"
    code = gen.main(
        [
            "--split",
            "train",
            "--registry",
            str(registry),
            "--prompt",
            str(prompt),
            "--briefs-out",
            str(out),
            "--salt-file",
            str(tmp_path / "salt"),
            "--dry-run",
        ]
    )
    assert code == 0
    assert "built" in capsys.readouterr().out
    assert all(json.loads(line)["intent"] for line in out.read_text().splitlines())
