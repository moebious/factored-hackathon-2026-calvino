"""Write the JSON Schema tool contracts to ``contracts/tools/`` (TSD-002).

Run after changing ``src/calvino/tools/contracts.py`` or a tool signature:
``uv run python scripts/export_tool_schemas.py``. A test fails if the files are out of date.
"""

from pathlib import Path

from calvino.tools.schemas import build_contract_files

if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "contracts" / "tools"
    out.mkdir(parents=True, exist_ok=True)
    for name, content in build_contract_files().items():
        (out / name).write_text(content, encoding="utf-8")
        print(f"wrote contracts/tools/{name}")
