"""Write the JSON Schema data contracts to ``contracts/data/`` (TSD-007).

Run after changing ``src/calvino/data/contracts.py``:
``uv run python scripts/export_data_schemas.py``. A test fails if the files are out of date.
"""

from pathlib import Path

from calvino.data.schemas import build_schema_files

if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "contracts" / "data"
    out.mkdir(parents=True, exist_ok=True)
    for name, content in build_schema_files().items():
        (out / name).write_text(content, encoding="utf-8")
        print(f"wrote contracts/data/{name}")
