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
from calvino.llm.hetzner import clients_from_env
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
    """Ask both providers what they serve. Returns one line per failure."""
    try:
        clients = clients_from_env()
    except LlmError as error:
        # Building both clients is also the check that the deployment has both roles configured,
        # so a missing key is reported rather than raised.
        return [f"the clients are not configured, so no catalogue was checked ({error.message})"]

    failures: list[str] = []
    for name, client in (("agent", clients.agent), ("judge", clients.judge)):
        try:
            served = client.list_models()
        except LlmError as error:
            failures.append(f"{name}: {providers.role(name).model} could not be checked ({error})")
            continue
        failures.extend(verify_catalogue(providers.role(name).model, served, role=name))
        recorded = _recorded_ids(providers, name)
        if recorded:
            extra = unrecorded(recorded, served)
            if extra:
                shown = ", ".join(extra[:3]) + (
                    f" and {len(extra) - 3} more" if len(extra) > 3 else ""
                )
                print(f"  note: {name} serves {len(extra)} id(s) not in the snapshot: {shown}")
    return failures


def _recorded_ids(providers: ProviderFile, role: str) -> tuple[str, ...]:
    for entry in providers.observed:
        if entry.role == role:
            return entry.ids
    return ()


if __name__ == "__main__":
    sys.exit(main())
