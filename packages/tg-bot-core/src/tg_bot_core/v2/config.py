from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class StartPolicy(StrEnum):
    RESET = "reset"
    RESUME = "resume"


@dataclass(frozen=True, slots=True)
class BotConfig:
    """Runtime configuration. All paths are project-local and explicit."""

    bot_id: str
    token: str | None
    resource_root: Path
    database_path: Path
    start_policy: StartPolicy = StartPolicy.RESET
    worker_count: int = 1
    max_auto_transitions: int = 32

    def __post_init__(self) -> None:
        if not self.bot_id.strip():
            raise ValueError("bot_id is required.")
        if self.worker_count < 1:
            raise ValueError("worker_count must be at least one.")
        if self.max_auto_transitions < 1:
            raise ValueError("max_auto_transitions must be at least one.")

    @classmethod
    def from_env(
        cls,
        *,
        bot_id: str = "bot",
        resource_root: str | Path = "resources",
        database_path: str | Path = "data/runtime.sqlite3",
        start_policy: StartPolicy = StartPolicy.RESET,
        worker_count: int = 1,
    ) -> "BotConfig":
        return cls(
            bot_id=bot_id,
            token=os.getenv("BOT_TOKEN"),
            resource_root=Path(resource_root).resolve(),
            database_path=Path(database_path).resolve(),
            start_policy=start_policy,
            worker_count=max(1, worker_count),
        )
