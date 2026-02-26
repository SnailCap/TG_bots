from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Optional

from core.src.interaction.exceptions.template_errors import PlaceholderFormatError


def format_text(template: str, variables: Mapping[str, Any]) -> str:
    try:
        return template.format(**variables)
    except Exception as e:
        raise PlaceholderFormatError(template, dict(variables), e)


def load_text_file(path: str | Path, *, encoding: str = "utf-8") -> str:
    p = Path(path)
    return p.read_text(encoding=encoding)


def load_and_format_text(
    *,
    base_dir: str | Path,
    text_file: str,
    variables: Mapping[str, Any],
    encoding: str = "utf-8",
) -> str:
    full_path = Path(base_dir) / text_file
    raw = load_text_file(full_path, encoding=encoding)
    return format_text(raw, variables)
