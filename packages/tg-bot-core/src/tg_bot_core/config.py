from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


_ENV_ASSIGNMENT = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")


@dataclass(frozen=True, slots=True)
class BotConfig:
    """Runtime-only configuration; application behavior lives in resources."""

    project_root: Path
    token: str | None
    database_path: Path
    worker_count: int = 1
    max_auto_transitions: int = 32

    def __post_init__(self) -> None:
        if self.worker_count < 1:
            raise ValueError("worker_count must be at least one.")
        if self.max_auto_transitions < 1:
            raise ValueError("max_auto_transitions must be at least one.")

    @property
    def resource_root(self) -> Path:
        return self.project_root / "resources"

    @classmethod
    def from_env(
        cls,
        *,
        project_root: str | Path = ".",
        database_path: str | Path = "data/runtime.sqlite3",
        worker_count: int = 1,
        max_auto_transitions: int = 32,
    ) -> "BotConfig":
        root = Path(project_root).resolve()
        database = Path(database_path)
        if not database.is_absolute():
            database = root / database
        return cls(
            project_root=root,
            token=os.getenv("BOT_TOKEN") or _project_env_value(root / ".env", "BOT_TOKEN"),
            database_path=database.resolve(),
            worker_count=worker_count,
            max_auto_transitions=max_auto_transitions,
        )


def _project_env_value(path: Path, key: str) -> str | None:
    """Read one runtime setting from a project-local .env without mutating process env."""

    if not path.is_file():
        return None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise RuntimeError(f"Cannot read project environment file: {path}") from error

    value: str | None = None
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _ENV_ASSIGNMENT.match(line)
        if match is None or match.group(1) != key:
            continue
        candidate = match.group(2).strip()
        if len(candidate) >= 2 and candidate[0] == candidate[-1] and candidate[0] in {"'", '"'}:
            candidate = candidate[1:-1]
        value = candidate or None
    return value
