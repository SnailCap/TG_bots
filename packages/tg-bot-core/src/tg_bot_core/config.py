from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


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
            token=os.getenv("BOT_TOKEN"),
            database_path=database.resolve(),
            worker_count=worker_count,
            max_auto_transitions=max_auto_transitions,
        )
