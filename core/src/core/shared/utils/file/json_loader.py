from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


def load_json(filepath: str | Path) -> Dict:
    path = Path(filepath)
    if not path.is_file():
        raise FileNotFoundError(path)

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_all_json_configs_from_path(path: str | Path, *, strict: bool = False) -> dict:
    """
    Loads and merges all .json files from the specified folder.

    Each file must contain a dictionary:
        { "entity_name": { ... }, ... }

    :param path: folder containing json files
    :param strict: raise error if duplicate keys are found
    """
    result = {}

    for json_path in Path(path).rglob("*.json"):
        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError(
                f"{json_path} must contain a JSON object (dict), not {type(data)}"
            )

        if strict:
            dupes = set(data.keys()) & set(result.keys())
            if dupes:
                raise ValueError(
                    f"Duplicate keys {sorted(dupes)} found in {json_path}"
                )

        result.update(data)

    return result