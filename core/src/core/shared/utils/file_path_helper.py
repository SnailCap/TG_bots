from __future__ import annotations

from pathlib import Path


def file_path(file: str) -> Path:
    return Path(file).resolve()


def parent(path: Path, levels: int) -> Path:
    if levels < 0:
        raise ValueError("levels must be >= 0")
    p = path
    for _ in range(levels):
        p = p.parent
    return p


def as_posix_str(path: Path) -> str:
    # consistent string path, handy for config values
    return str(path)