"""Draft the message set with the agent-role LLM (TSD-019, T-106).

Keyed generation only: refuses to draft without ``CALVINO_LLM_*`` (keys
come from the maintainer's env file outside every worktree and never
appear in logs, files or review output). Every test and check stays
offline: ``--dry-run`` builds briefs and validates registries with no
client, and the unit tests use a fake client.

Pacing follows the provider's documented cap (10 requests per 60 s):
the client's rate limiter spaces calls, so a full split takes hours
and is run per split, not per row.

Typical invocations (keys loaded from outside every worktree)::

    set -a; source "$CALVINO_ENV_FILE"; set +a
    uv run python scripts/generate_message_set.py --split train \\
        --registry evaluation/message-set/v1/seeds.train.jsonl \\
        --briefs /tmp/briefs.train.jsonl --out /tmp/train.jsonl
    uv run python scripts/generate_message_set.py --split test \\
        --merge-hand-written evaluation/message-set/v1/test-hand-written.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import stat
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from calvino.data.message_set import (  # noqa: E402
    MessageLabels,
    MessageOracleFacts,
    MessageProvenance,
    MessageRow,
    RecordFacts,
    SeedRow,
    check_intra_set,
    check_no_records_committed,
    derive_defaults,
    derive_seed_key,
    gate_table_hash,
    salted_customer_hash,
)
from calvino.llm.contracts import ChatRequest, Message, MessageRole, Role  # noqa: E402
from calvino.llm.errors import LlmError  # noqa: E402
from calvino.policy.config import load_policy  # noqa: E402

SET_VERSION = "v1"

# The agent-role models are reasoning models: one three-sentence reply used 3,064 completion tokens
# [measured, 2026-10-04], and a 256-token budget ended every call with LLM-TRUNCATED and no text.
DRAFT_COMPLETION_BUDGET = 8192
DEFAULT_SALT_FILE = Path("data/message-set-salt-v1")
DEFAULT_POINTER_LOG = Path("data/message-set-seed-log.jsonl")

LANGUAGE_BY_COUNTRY = {"MX": "es-MX", "CO": "es-CO", "AR": "es-AR"}


def is_git_ignored(path: Path) -> bool:
    """Whether git would ignore this path. Fail closed: any git error
    means not ignored, so the salt is never written on a guess."""
    try:
        return (
            subprocess.run(
                ["git", "check-ignore", "-q", str(path)],
                check=False,
                capture_output=True,
            ).returncode
            == 0
        )
    except OSError:
        return False


def ensure_salt(salt_file: Path) -> str:
    """Load the per-version secret salt, creating it once with owner-only
    permissions. Refuses a path git would commit: the salt is never committed."""
    if not is_git_ignored(salt_file):
        raise SystemExit(f"refusing: salt file {salt_file} is not git-ignored")
    if salt_file.exists():
        return salt_file.read_text(encoding="utf-8").strip()
    salt_file.parent.mkdir(parents=True, exist_ok=True)
    value = secrets.token_hex(32)
    descriptor = os.open(salt_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(value + "\n")
    try:
        salt_file.chmod(0o600)
    except OSError:
        pass
    mode = stat.S_IMODE(salt_file.stat().st_mode)
    if mode & 0o077:
        raise SystemExit(f"refusing: salt file {salt_file} is group/world readable")
    print(f"created per-version salt at {salt_file} (secret, git-ignored)")
    return value


def build_brief_markdown(seed: SeedRow, brief: dict) -> str:
    """The per-seed brief appended to the prompt: intent, variant, facts."""
    facts = seed.record_facts
    lines = [
        f"intent: {brief['intent']}",
        f"country_variant: {seed.country_variant}",
        f"persona_voice: {brief.get('persona_voice', 'varied, natural')}",
    ]
    if brief.get("adversarial_kind"):
        lines.append(f"adversarial_kind: {brief['adversarial_kind']}")
    if brief.get("parent_message"):
        lines.append(f"parent_message: {brief['parent_message']}")
    fact_bits = []
    for name in ("status", "transaction_type", "currency", "channel"):
        value = getattr(facts, name)
        if value is not None:
            fact_bits.append(f"{name}={value}")
    if facts.amount_band is not None:
        fact_bits.append(f"amount_band={facts.amount_band}")
    if facts.complaint_status is not None:
        fact_bits.append(f"complaint_status={facts.complaint_status}")
    if facts.sla_state is not None:
        fact_bits.append(f"sla_state={facts.sla_state}")
    lines.append(f"seed_facts: {'; '.join(fact_bits) or 'none (no record)'}")
    return "\n".join(lines)


def draft_message(
    client: object, system_prompt: str, brief_markdown: str, purpose: str
) -> tuple[str, str]:
    """One keyed drafting call. Returns the message text and the model id."""
    request = ChatRequest(
        role=Role.AGENT,
        messages=(
            Message(role=MessageRole.SYSTEM, content=system_prompt),
            Message(role=MessageRole.USER, content=brief_markdown),
        ),
        purpose=purpose,
        max_tokens=DRAFT_COMPLETION_BUDGET,
    )
    response = client.complete(request)  # type: ignore[union-attr]
    model_id = getattr(client, "model", "") or os.environ.get("CALVINO_LLM_MODEL", "")
    return response.text.strip(), model_id


def message_for_seed(
    *,
    seed: SeedRow,
    brief: dict,
    text: str,
    model_id: str,
    prompt_version: str,
    msg_id: str,
) -> MessageRow:
    """Defaults, provenance and schema around one drafted text."""
    labels, facts = derive_defaults(
        brief_intent=brief["intent"],
        adversarial_kind=brief.get("adversarial_kind"),
        seed_kind=seed.kind,
    )
    return MessageRow(
        msg_id=msg_id,
        split=seed.split,
        language_variant=LANGUAGE_BY_COUNTRY[seed.country_variant],
        message=text,
        seed_key=seed.seed_key,
        labels=labels,
        oracle_facts=MessageOracleFacts(
            intent=facts.intent,
            ambiguous=facts.ambiguous,
            status=facts.status,
            owner=facts.owner,
            amount_band=seed.record_facts.amount_band or facts.amount_band,
            fraud_flag=seed.record_facts.fraud_flag,
            in_scope=facts.in_scope,
        ),
        provenance=MessageProvenance(
            prompt_id=seed.prompt_id,
            prompt_version=prompt_version,
            model_id=model_id,
            generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
            review_verdict="unreviewed",
        ),
        synthetic=True,
    )


def read_jsonl(path: Path, model: type) -> list:
    """Parse and validate one JSONL file, one row per line for reviewable diffs."""
    rows = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if line.strip():
                try:
                    rows.append(model.model_validate(json.loads(line)))
                except ValueError as error:
                    raise SystemExit(f"{path}:{number}: invalid row: {error}") from error
    return rows


def verify_regeneration(salt: str, pointer_log: Path) -> int:
    """Recompute every keyed hash from the salt and the pointer log.

    Returns the checked count; raises on the first mismatch, so a lost
    or rotated salt is loud instead of silent.
    """
    checked = 0
    with pointer_log.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            entry = json.loads(line)
            expected = derive_seed_key(
                salt=salt,
                set_version=entry["set_version"],
                split=entry["split"],
                kind=entry["kind"],
                record_id=entry["record_id"],
                role=entry.get("role", "base"),
            )
            if expected != entry["seed_key"]:
                raise SystemExit(f"pointer log mismatch for {entry['seed_key']}")
            hashed = salted_customer_hash(entry["customer_id"], salt)
            if hashed != entry["customer_hash"]:
                raise SystemExit(f"customer hash mismatch for {entry['seed_key']}")
            checked += 1
    return checked


def merge_hand_written(
    *,
    salt: str,
    source: Path,
    msg_prefix: str = "test-hand",
    gate_limits: dict[str, float] | None = None,
) -> tuple[list[MessageRow], list[SeedRow]]:
    """Key the team-written supplement: nominal persona ids become
    salted-hash keys under the set version's salt at merge time, so the
    committed supplement carries no key material before review. Any raw
    ``amount`` in the supplement's nominal facts is dropped at the gate
    (bands only); banded rows hash the evaluated gate table, so the
    oracle-path guard holds for merged rows too."""
    messages: list[MessageRow] = []
    seeds: list[SeedRow] = []
    with source.open(encoding="utf-8") as handle:
        for index, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            persona_id = row.pop("persona_id")
            event_date = row.pop("event_date")
            country = row.pop("country_variant")
            kind = row.pop("kind", "hand_written")
            facts_dict = row.pop("record_facts")
            facts_dict.pop("amount", None)  # nominal amounts never merge
            record_facts = RecordFacts.model_validate(facts_dict)
            if record_facts.amount_band is not None and gate_limits is None:
                raise SystemExit("banded hand-written rows need the evaluated gate table")
            table_hash = (
                gate_table_hash(gate_limits) if record_facts.amount_band is not None else None
            )
            seed_key = derive_seed_key(
                salt=salt,
                set_version=SET_VERSION,
                split="test",
                kind=kind,
                record_id=persona_id,
            )
            seeds.append(
                SeedRow(
                    seed_key=seed_key,
                    split="test",
                    prompt_id="hand-written",
                    kind=kind,
                    customer_hash=salted_customer_hash(persona_id, salt),
                    country_variant=country,
                    record_facts=record_facts,
                    event_date=event_date,
                    policy_version=row.get("policy_version", "v2"),
                    gate_table_hash=table_hash,
                )
            )
            messages.append(
                MessageRow(
                    msg_id=f"{msg_prefix}-{index:02d}",
                    split="test",
                    language_variant=row["language_variant"],
                    message=row["message"],
                    seed_key=seed_key,
                    labels=MessageLabels.model_validate(row["labels"]),
                    oracle_facts=MessageOracleFacts.model_validate(row["oracle_facts"]),
                    provenance=MessageProvenance(
                        prompt_id="hand-written",
                        prompt_version=SET_VERSION,
                        model_id="hand-written",
                        reviewer=row.get("reviewer", ""),
                        review_verdict=row.get("review_verdict", "unreviewed"),
                    ),
                    synthetic=True,
                )
            )
    return messages, seeds


def main(argv: list[str] | None = None) -> int:
    """Draft one split's messages, then validate L1-L5 and the scans."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--split", choices=("train", "calibration", "test"), required=True)
    parser.add_argument("--registry", type=Path, help="seeds.{split}.jsonl to draft from")
    parser.add_argument("--briefs", type=Path, help="JSONL of {seed_key, intent, ...} briefs")
    parser.add_argument("--prompt", type=Path, help="the versioned prompt markdown")
    parser.add_argument("--prompt-version", default=SET_VERSION)
    parser.add_argument("--out", type=Path, help="where to write message JSONL")
    parser.add_argument("--limit", type=int, default=None, help="draft at most N rows")
    parser.add_argument("--salt-file", type=Path, default=DEFAULT_SALT_FILE)
    parser.add_argument("--pointer-log", type=Path, default=DEFAULT_POINTER_LOG)
    parser.add_argument("--merge-hand-written", type=Path, default=None)
    parser.add_argument("--hand-written-seeds-out", type=Path, default=None)
    parser.add_argument("--policy", type=Path, default=None)
    parser.add_argument("--verify", type=Path, default=None, help="verify a pointer log and exit")
    parser.add_argument("--dry-run", action="store_true", help="briefs and checks only, no LLM")
    args = parser.parse_args(argv)

    salt = ensure_salt(args.salt_file)
    if args.verify is not None:
        checked = verify_regeneration(salt, args.verify)
        print(f"pointer log ok: {checked} keys recomputed")
        return 0

    if args.merge_hand_written is not None:
        if args.split != "test":
            print("hand-written rows merge into test only", file=sys.stderr)
            return 2
        messages, seeds = merge_hand_written(
            salt=salt,
            source=args.merge_hand_written,
            gate_limits=dict(load_policy(args.policy).gate.allow_amount_limit)
            if args.policy
            else dict(load_policy().gate.allow_amount_limit),
        )
        print(f"keyed {len(messages)} hand-written rows (model_id hand-written)")
        if args.out is not None:
            with args.out.open("w", encoding="utf-8") as handle:
                for row in messages:
                    handle.write(row.model_dump_json() + "\n")
        if args.hand_written_seeds_out is not None:
            with args.hand_written_seeds_out.open("w", encoding="utf-8") as handle:
                for row in seeds:
                    handle.write(row.model_dump_json() + "\n")
        return 0

    for required in ("registry", "briefs", "prompt", "out"):
        if getattr(args, required) is None and not args.dry_run:
            print(f"--{required} is required without --dry-run", file=sys.stderr)
            return 2
    seeds = read_jsonl(args.registry, SeedRow)
    briefs = {}
    with args.briefs.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                briefs[row["seed_key"]] = row
    system_prompt = args.prompt.read_text(encoding="utf-8")

    client = None
    if not args.dry_run:
        from calvino.llm.hetzner import hetzner_client_from_env

        try:
            client = hetzner_client_from_env()
        except LlmError as error:
            print(f"not drafting: {error.message}", file=sys.stderr)
            return 2

    drafted: list[MessageRow] = []
    drafted_seeds: list[SeedRow] = []
    for index, seed in enumerate(seeds):
        if args.limit is not None and index >= args.limit:
            break
        brief = briefs.get(seed.seed_key)
        if brief is None:
            print(f"no brief for seed {seed.seed_key}, skipping")
            continue
        markdown = build_brief_markdown(seed, brief)
        if args.dry_run:
            text, model_id = f"<dry-run:{seed.seed_key}>", "dry-run"
        else:
            assert client is not None
            text, model_id = draft_message(
                client, system_prompt, markdown, f"message-set:{args.split}:{seed.seed_key}"
            )
        drafted.append(
            message_for_seed(
                seed=seed,
                brief=brief,
                text=text,
                model_id=model_id,
                prompt_version=args.prompt_version,
                msg_id=f"{args.split}-{index + 1:04d}",
            )
        )
        drafted_seeds.append(seed)

    if args.dry_run:
        print(f"dry run: {len(drafted)} briefs built, no calls made")
        return 0

    problems = check_intra_set(drafted, {})
    problems.extend(check_no_records_committed(drafted_seeds, drafted, set()))
    if problems:
        for violation in problems:
            print(f"FAILED: {violation.rule_id} {violation.detail}", file=sys.stderr)
        return 1

    with args.out.open("w", encoding="utf-8") as handle:
        for row in drafted:
            handle.write(row.model_dump_json() + "\n")
    print(f"drafted {len(drafted)} messages to {args.out} (model recorded per row)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
