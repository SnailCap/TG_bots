from __future__ import annotations

from pathlib import Path


def resolve_text_value(value: str, *, base_dir: Path) -> str:
    """Resolve the 'text' field.

    If a value looks like a .txt path, load it from base_dir / value.
    Otherwise, treat value as an inline text template.
    """
    if not value:
        return ""

    v = str(value)
    if v.lower().endswith(".txt"):
        path = (base_dir / v).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        return path.read_text(encoding="utf-8")
    return v
