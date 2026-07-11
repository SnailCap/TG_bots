from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path, PurePosixPath

from app.errors import UnsafePathError

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


def require_safe_identifier(value: str, *, label: str = "identifier") -> str:
    normalized = value.strip()
    if not _SAFE_IDENTIFIER.fullmatch(normalized):
        raise UnsafePathError(
            f"Invalid {label}: {value!r}",
            details={"label": label},
        )
    return normalized


def normalize_script_path(relative_path: str) -> str:
    normalized = normalize_relative_path(relative_path, label="script")
    path = PurePosixPath(normalized)
    if path.suffix.lower() != ".py":
        raise UnsafePathError("Script files must use the .py extension")
    return path.as_posix()


def normalize_asset_path(relative_path: str) -> str:
    return normalize_relative_path(relative_path, label="asset")


def normalize_relative_path(relative_path: str, *, label: str) -> str:
    raw = relative_path.strip().replace("\\", "/")
    if not raw or ":" in raw:
        raise UnsafePathError(f"{label.title()} path must be a non-empty relative path")
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise UnsafePathError(f"Unsafe {label} path: {relative_path!r}")
    return path.as_posix()


def safe_child(root: Path, *parts: str) -> Path:
    base = root.expanduser().resolve(strict=False)
    candidate = base.joinpath(*parts).resolve(strict=False)
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise UnsafePathError(f"Path escapes project root: {candidate}") from exc
    return candidate


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
