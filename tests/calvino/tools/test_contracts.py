"""Contract tests (TSD-002): generated schemas are current; fixture uses only the allowed codes."""

from __future__ import annotations

from pathlib import Path

from tests.calvino.tools.conftest import load_fixture

from calvino.tools.schemas import build_contract_files

CONTRACTS = Path(__file__).resolve().parents[3] / "contracts" / "tools"


def test_contract_files_match_the_models() -> None:
    expected = build_contract_files()
    assert {p.name for p in CONTRACTS.glob("*.json")} == set(expected)
    for name, content in expected.items():
        assert (CONTRACTS / name).read_text(encoding="utf-8") == content, (
            f"{name} is out of date: run `uv run python scripts/export_tool_schemas.py`"
        )


def test_no_tool_takes_a_session_or_customer_argument() -> None:
    import json

    tools = json.loads((CONTRACTS / "tools.json").read_text(encoding="utf-8"))
    assert len(tools) == 10
    for tool in tools:
        names = set(tool["input_schema"].get("properties", {}))
        assert not {n for n in names if "session" in n or "customer" in n}, tool["name"]


def test_fixture_is_labelled_synthetic_and_uses_only_allowed_codes() -> None:
    data = load_fixture()
    assert data["_label"].startswith("SYNTHETIC")
    assert {c["country"] for c in data["customers"]} <= {"MX", "CO", "AR", "US"}
    assert {e["country"] for e in data["entries"] if "country" in e} <= {"MX", "CO", "AR", "US"}
    currencies = {a["currency"] for a in data["accounts"]} | {
        e["currency"] for e in data["entries"]
    }
    assert currencies <= {"MXN", "COP", "ARS", "USD"}
