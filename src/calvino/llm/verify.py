"""Check a configured model against what a provider actually serves (TSD-009, decision 29).

A model id can stop being served: the provider retires it, renames it, or the configured value was
never right. That would otherwise surface as a failed call on a live customer request. This turns
it into a check that names the configured id, what the provider serves instead, and the nearest
ids it does serve, so the fix is obvious.

Kept apart from ``OpenAiCompatibleClient`` on purpose: the check needs the network, the client must
work without it, and a provider that is briefly unavailable must not stop the service from starting
(NFR-5). Nothing here is called at startup; ``scripts/check_providers.py`` gates the deploy.
"""

from __future__ import annotations

from difflib import get_close_matches

# How similar a served id has to be to be worth suggesting. Provider ids are long and share long
# prefixes, so this is deliberately tight: a suggestion that is not the right model is worse than
# none.
SUGGESTION_CUTOFF = 0.6


def verify_catalogue(model: str, served: tuple[str, ...], *, role: str = "") -> tuple[str, ...]:
    """Return one or two problem lines when ``model`` is not served; empty when it is.

    ``served`` is what the provider's models endpoint returned. The nearest served ids are named
    because the usual causes are a rename and a typo, and both are one edit away.
    """
    if model in served:
        return ()
    label = f"{role}: " if role else ""
    listed = ", ".join(served) if served else "none"
    lines = [f"{label}{model} is not served; the provider serves {len(served)} model(s): {listed}"]
    # Substring first: providers often re-suffix rather than rename ("...-0813" -> "..."), and the
    # rest of the id then matches exactly, which no closeness ratio would rank first.
    related = [candidate for candidate in served if model in candidate or candidate in model]
    near = get_close_matches(model, served, n=3, cutoff=SUGGESTION_CUTOFF)
    suggestions = [candidate for candidate in related + near if candidate != model]
    if suggestions:
        lines.append(f"{label}did you mean: {', '.join(dict.fromkeys(suggestions))}?")
    return tuple(lines)


def unrecorded(recorded: tuple[str, ...], served: tuple[str, ...]) -> tuple[str, ...]:
    """Ids the provider serves that the recorded snapshot does not list. Informational.

    Only one direction is meaningful: the snapshot lists the pinned model and its alternative, not
    everything the provider has, so a "retired" id is never evidence of anything. A provider adding
    models is normal (Hetzner says its selection will change), so this is a note to re-read
    ``providers.yaml``, never a failure.
    """
    return tuple(candidate for candidate in served if candidate not in recorded)
