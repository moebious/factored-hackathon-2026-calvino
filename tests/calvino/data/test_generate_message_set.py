"""Tests for the keyed message-set runner's offline paths (TSD-019).

The fake client stands in for the provider: no network, no keys, no
dataset, no salt. Live drafting is exercised only by the maintainer's
keyed invocation, never here.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import generate_message_set as gen

from calvino.data.message_set import SeedRow

SEED = {
    "seed_key": "v1-t1",
    "split": "train",
    "prompt_id": "train-v1",
    "kind": "problem_transaction",
    "customer_hash": "a" * 16,
    "country_variant": "MX",
    "record_facts": {"kind": "problem_transaction", "status": "Pending", "currency": "MXN"},
    "event_date": "2024-03-10",
    "policy_version": "v2",
}
BRIEF = {"seed_key": "v1-t1", "intent": "cancel", "persona_voice": "terse, calm"}


class FakeClient:
    """A canned provider: records purposes, never touches the network."""

    def __init__(self, text="Quiero cancelar mi transferencia pendiente"):
        self.text = text
        self.model = "fake-model"
        self.purposes = []

    def complete(self, request):
        self.purposes.append(request.purpose)

        class Response:
            text = self.text

        return Response()


def write(path: Path, rows: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    return path


def test_brief_names_intent_variant_and_facts():
    """The brief carries everything the prompt needs and nothing else."""
    seed = SeedRow.model_validate(SEED)
    markdown = gen.build_brief_markdown(seed, BRIEF)
    assert "intent: cancel" in markdown
    assert "country_variant: MX" in markdown
    assert "status=Pending" in markdown
    assert "customer" not in markdown.replace("persona_voice", "")


def test_dry_run_builds_briefs_without_keys(tmp_path, monkeypatch):
    """Dry runs never construct a client, so missing keys cannot matter."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(gen, "is_git_ignored", lambda path: True)
    registry = write(tmp_path / "seeds.jsonl", [SEED])
    briefs = write(tmp_path / "briefs.jsonl", [BRIEF])
    prompt = tmp_path / "prompt.md"
    prompt.write_text("draft plainly", encoding="utf-8")
    salt = tmp_path / "salt"
    code = gen.main(
        [
            "--split",
            "train",
            "--registry",
            str(registry),
            "--briefs",
            str(briefs),
            "--prompt",
            str(prompt),
            "--out",
            str(tmp_path / "out.jsonl"),
            "--salt-file",
            str(salt),
            "--dry-run",
        ]
    )
    assert code == 0
    assert salt.exists()


def test_salt_refuses_a_committable_path(tmp_path, monkeypatch):
    """A salt file git would commit is refused, never written."""
    monkeypatch.setattr(gen, "is_git_ignored", lambda path: False)
    candidate = tmp_path / "salt-v1"
    try:
        gen.ensure_salt(candidate)
    except SystemExit as error:
        assert "git-ignored" in str(error)
    else:
        raise AssertionError("a committable salt path must be refused")
    assert not candidate.exists()


def test_salt_guard_fails_closed_on_git_errors(monkeypatch):
    """When git cannot answer, the path counts as committable: fail closed."""
    monkeypatch.setattr(
        gen.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("no git"))
    )
    assert gen.is_git_ignored(Path("data/message-set-salt-v1")) is False


def test_keyed_run_with_fake_client(tmp_path):
    """End to end with a fake provider: defaults, provenance, clean scans."""
    seed = SeedRow.model_validate(SEED)
    text, model_id = gen.draft_message(FakeClient(), "prompt", "brief", "purpose")
    assert text and model_id == "fake-model"
    row = gen.message_for_seed(
        seed=seed,
        brief=BRIEF,
        text=text,
        model_id=model_id,
        prompt_version="v1",
        msg_id="train-0001",
    )
    assert row.labels.stuck_intent == "cancel"
    assert row.oracle_facts.intent == "cancel"
    assert row.provenance.review_verdict == "unreviewed"
    assert row.synthetic is True


def test_hand_written_merge_keys_at_merge_time(tmp_path):
    """Nominal persona ids become salted keys only when merged, and the
    committed supplement carries no key material."""
    supplement = tmp_path / "hand.jsonl"
    supplement.write_text(
        json.dumps(
            {
                "persona_id": "persona-mx-hand-01",
                "event_date": "2026-03-01",
                "country_variant": "MX",
                "kind": "hand_written",
                "record_facts": {"kind": "hand_written", "status": "Declined"},
                "language_variant": "es-MX",
                "message": "Se me duplicó un cargo ayer, ¿me ayudas a revisarlo?",
                "labels": {
                    "workflow_area": "stuck payment",
                    "stuck_intent": "status",
                    "clear_enough": True,
                    "needs_person": False,
                    "injection": False,
                },
                "oracle_facts": {
                    "intent": "explain",
                    "ambiguous": False,
                    "status": None,
                    "owner": True,
                    "amount_band": "under_gate",
                    "fraud_flag": False,
                    "in_scope": True,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert "seed_key" not in supplement.read_text(encoding="utf-8")
    messages, seeds = gen.merge_hand_written(salt="s", source=supplement)
    assert messages[0].seed_key == seeds[0].seed_key
    assert messages[0].provenance.model_id == "hand-written"
    assert messages[0].msg_id == "test-hand-01"
    assert "persona-mx-hand-01" not in messages[0].seed_key


def test_pointer_log_round_trip(tmp_path):
    """Keys recomputed from salt and pointer log match what was logged."""
    log = tmp_path / "log.jsonl"
    log.write_text(
        json.dumps(
            {
                "seed_key": gen.derive_seed_key(
                    salt="s",
                    set_version="v1",
                    split="train",
                    kind="problem_transaction",
                    record_id="r1",
                ),
                "set_version": "v1",
                "split": "train",
                "kind": "problem_transaction",
                "record_id": "r1",
                "role": "base",
                "customer_id": "C-1",
                "customer_hash": gen.salted_customer_hash("C-1", "s"),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert gen.verify_regeneration("s", log) == 1
