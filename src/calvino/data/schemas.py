"""JSON Schemas of the data contracts (TSD-007), written to ``contracts/data/``.

Each table's schema is its row model's JSON Schema plus the primary key, the required
columns, the foreign keys and the rules that apply to it, so a reader outside Python sees
the whole contract in one file.
"""

from __future__ import annotations

import json

from calvino.data.contracts import TABLES, rules_for


def build_schema_files() -> dict[str, str]:
    """File name -> JSON text for every table contract, deterministic and sorted."""
    files: dict[str, str] = {}
    for name, contract in TABLES.items():
        schema = contract.model.model_json_schema()
        schema["title"] = name
        schema["x-calvino"] = {
            "primary_key": list(contract.primary_key),
            "required_columns": list(contract.required),
            "foreign_keys": [
                {
                    "column": fk.column,
                    "references": f"{fk.parent}.{fk.parent_column}",
                    "severity": fk.severity.value,
                }
                for fk in contract.foreign_keys
            ],
            "rules": [
                {
                    "id": r.rule_id,
                    "severity": r.severity.value,
                    "violation": r.predicate,
                    "meaning": r.meaning,
                }
                for r in rules_for(name)
            ],
        }
        files[f"{name}.schema.json"] = json.dumps(schema, indent=2, ensure_ascii=False) + "\n"
    return files
