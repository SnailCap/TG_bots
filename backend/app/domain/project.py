from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class BotIdentity:
    bot_id: int
    username: str
    display_name: str


@dataclass(frozen=True, slots=True)
class BotConfiguration:
    secret_ref: str | None = None
    start_flow_id: str | None = None
    identity: BotIdentity | None = None
    start_behavior: str = "reset"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BotProject:
    id: str
    name: str
    configuration: BotConfiguration = field(default_factory=BotConfiguration)
    schema_version: int = 1
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @classmethod
    def create(cls, name: str) -> "BotProject":
        normalized = name.strip()
        if not normalized:
            raise ValueError("Project name must not be empty")
        return cls(id=str(uuid4()), name=normalized)


@dataclass(frozen=True, slots=True)
class RecentProject:
    project_id: str
    name: str
    path: str
    last_opened_at: datetime = field(default_factory=utc_now)
    exists: bool = True


@dataclass(frozen=True, slots=True)
class ProjectTreeEntry:
    name: str
    path: str
    kind: str
    id: str = ""
    children: tuple["ProjectTreeEntry", ...] = ()
    size: int | None = None
