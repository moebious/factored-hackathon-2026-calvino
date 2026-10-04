"""The import cycle that made ``pytest tests/calvino/hub`` fail on its own (TSD-003).

Each case runs in a fresh interpreter. That is the point: inside a full test
run something else always imports ``calvino.api`` first, which hides the cycle
completely, so testing it in-process would prove nothing.
"""

from __future__ import annotations

import importlib
import subprocess
import sys

import pytest

import calvino.api

# Names a caller may use, kept explicit so a dropped export fails here.
PUBLIC_NAMES = [
    "ApiSettings",
    "DemoAnswer",
    "DemoDecideRequest",
    "DemoDecision",
    "FixtureFraudContext",
    "HubMessageRequest",
    "HubResumeRequest",
    "LayaLoader",
    "SystemOneLoader",
    "build_demo_hub",
    "create_app",
    "run_demo_decision",
    "scores_from_answers",
    "settings_from_env",
]


def imports_cleanly(statement: str) -> None:
    """Import ``statement`` in a fresh interpreter, failing loudly on any error."""
    result = subprocess.run(
        [sys.executable, "-c", statement],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"{statement!r} failed in a fresh interpreter:\n{result.stderr.strip()}"
    )


@pytest.mark.parametrize(
    "statement",
    [
        "import calvino.hub",
        "from calvino.hub import TemplateAgent",
        # The path the cycle actually took: a submodule import runs the package __init__.
        "from calvino.api.decide import scores_from_answers",
        "from calvino.api.loader import SystemOneLoader",
        "import calvino.api",
    ],
    ids=["hub", "hub-symbol", "api-decide", "api-loader", "api"],
)
def test_the_packages_import_in_any_order(statement):
    imports_cleanly(statement)


@pytest.mark.parametrize("name", PUBLIC_NAMES)
def test_every_public_name_still_resolves(name):
    """Deferring the imports must not change what callers can import."""
    assert getattr(calvino.api, name) is not None


def test_an_unknown_name_still_raises_attribute_error():
    # Held in a variable so this reads as a deliberate lookup rather than a stray expression.
    missing = "not_a_real_name"
    with pytest.raises(AttributeError):
        getattr(calvino.api, missing)


def test_the_public_names_are_listed_for_tab_completion():
    assert sorted(calvino.api.__all__) == sorted(PUBLIC_NAMES)
    assert sorted(dir(calvino.api)) == sorted(PUBLIC_NAMES)


def test_every_exported_name_maps_to_a_submodule_that_defines_it():
    """__all__ is a literal list for readers and linters; this is what keeps it honest."""
    assert sorted(calvino.api._SUBMODULES) == sorted(calvino.api.__all__)
    for name, module_name in calvino.api._SUBMODULES.items():
        module = importlib.import_module(module_name)
        assert hasattr(module, name), f"{module_name} does not define {name}"
