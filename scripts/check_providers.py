"""Check the language models against the committed record and the providers' catalogues.

``uv run python scripts/check_providers.py``
``uv run python scripts/check_providers.py --config-only``

Two checks, because they answer different questions. *Config drift* compares the deployed
environment variables with ``providers.yaml``, with no network. *Catalogue* asks each provider
what it serves and fails when a configured id is not there, with the nearest ids it does serve.

The live check needs a key for each provider and is skipped with a message when one is missing,
so this also runs offline. Exits 1 on any failure.

Deliberately not called at startup: a network call there would take the public demo link down
whenever the provider is briefly unavailable (NFR-5). This gates the deploy instead.
"""

import argparse
import sys
from pathlib import Path

from calvino.llm.errors import LlmError
from calvino.llm.hetzner import hetzner_client_from_env, judge_client_from_env
from calvino.llm.providers import ProviderFile, configuration_problems, load_providers
from calvino.llm.verify import unrecorded, verify_catalogue


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--config-only",
        action="store_true",
        help="only compare the environment with providers.yaml, without asking the providers",
    )
    parser.add_argument(
        "--providers",
        type=Path,
        default=None,
        help="path to the provider record (defaults to the repository's providers.yaml)",
    )
    args = parser.parse_args()

    providers = load_providers(args.providers) if args.providers else load_providers()
    print(f"providers.yaml {providers.version}")
    for name in ("agent", "judge"):
        role = providers.role(name)
        print(f"  {name}: {role.model} on {role.provider} (pin: {role.pin})")

    failures = list(configuration_problems(providers))
    if not args.config_only:
        failures.extend(check_catalogue(providers))
    for failure in failures:
        print(f"  FAILED: {failure}")
    if not failures:
        print("  ok")
    return 1 if failures else 0


def check_catalogue(providers: ProviderFile) -> list[str]:
    """Ask each configured role's provider what it serves. Returns one line per failure.

    Each role is built on its own, so a deployment that has the agent live and the judge not
    yet configured can still check the agent. A role that is not configured is a note, not a
    failure; only having nothing to check at all is a failure.
    """
    builders = {"agent": hetzner_client_from_env, "judge": judge_client_from_env}

    failures: list[str] = []
    checked = 0
    for role, build in builders.items():
        try:
            client = build()
        except LlmError as error:
            # The exception names the variable that is missing, which is the whole point of the
            # check; a generic "not configured" note sent us after the wrong variable once already.
            print(f"  note: {role} not checked: {error.message}")
            continue
        checked += 1
        try:
            served = client.list_models()
        except LlmError as error:
            failures.append(f"{role}: {providers.role(role).model} could not be checked ({error})")
            continue
        # Check the id the client is actually configured with. When a role runs its staging model
        # the provider asked is the staging provider, so asking it about the production id asks a
        # question with no answer; configuration_problems is what decides whether the pairing is
        # one the record allows.
        if client.model != providers.role(role).model:
            print(f"  {role}: checking its configured {client.model} against the catalogue")
        failures.extend(verify_catalogue(client.model, served, role=role))
        recorded = _recorded_ids(providers, role)
        if recorded:
            extra = unrecorded(recorded, served)
            if extra:
                shown = ", ".join(extra[:3]) + (
                    f" and {len(extra) - 3} more" if len(extra) > 3 else ""
                )
                print(f"  note: {role} serves {len(extra)} id(s) not in the snapshot: {shown}")

    if not checked:
        failures.append("neither role is configured, so no provider was asked what it serves")
    return failures


def _recorded_ids(providers: ProviderFile, role: str) -> tuple[str, ...]:
    for entry in providers.observed:
        if entry.role == role:
            return entry.ids
    return ()


if __name__ == "__main__":
    sys.exit(main())
