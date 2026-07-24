from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from .errors import SecretDetected


_SENSITIVE_PATHS = {
    ".env",
    "data/runtime.sqlite3",
    "data/runtime.sqlite3-wal",
    "data/runtime.sqlite3-shm",
}
_SECRET_PATTERNS = (
    re.compile(rb"\b\d{6,12}:[A-Za-z0-9_-]{30,}\b"),
    re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)
_MAX_SCAN_BYTES = 2_000_000


def ensure_gitignore(root: Path) -> None:
    required = (
        ".env",
        ".venv/",
        "data/*.sqlite3",
        "data/*.sqlite3-wal",
        "data/*.sqlite3-shm",
        "__pycache__/",
        "*.py[cod]",
        ".pytest_cache/",
        ".idea/",
        ".vscode/",
        ".botstudio/backups/",
        ".botstudio/*.credentials*",
        "build/",
        "dist/",
    )
    path = root / ".gitignore"
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    normalized = {line.strip() for line in existing}
    missing = [line for line in required if line not in normalized]
    if missing:
        content = "\n".join(existing + missing).strip() + "\n"
        path.write_text(content, encoding="utf-8", newline="\n")


def scan_for_secrets(root: Path, relative_paths: Iterable[str]) -> None:
    findings: list[str] = []
    for relative in relative_paths:
        normalized = relative.replace("\\", "/").lstrip("./")
        if normalized in _SENSITIVE_PATHS or normalized.startswith(".venv/"):
            findings.append(normalized)
            continue
        path = (root / normalized).resolve(strict=False)
        if not path.is_file() or not path.is_relative_to(root.resolve()):
            continue
        try:
            if path.stat().st_size > _MAX_SCAN_BYTES:
                continue
            content = path.read_bytes()
        except OSError:
            continue
        if b"\x00" in content[:8192]:
            continue
        if any(pattern.search(content) for pattern in _SECRET_PATTERNS):
            findings.append(normalized)
    if findings:
        raise SecretDetected(
            "Push blocked because possible credentials were found.",
            details={"files": sorted(set(findings))},
        )

