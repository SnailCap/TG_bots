from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .enums import ActionResultStatus, RuntimeState
from .project import BotIdentity, utc_now


@dataclass(frozen=True, slots=True)
class RuntimeResult:
    status: ActionResultStatus
    next_transition: str | None = None
    variables: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BotRuntimeStatus:
    state: RuntimeState = RuntimeState.STOPPED
    project_id: str | None = None
    bot_identity: BotIdentity | None = None
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    last_error: str | None = None


@dataclass(frozen=True, slots=True)
class RuntimeHistoryEntry:
    project_id: str
    event_type: str
    message: str
    level: str = "info"
    session_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    id: int | None = None


@dataclass(frozen=True, slots=True)
class RuntimeEvent:
    project_id: str | None
    category: str
    message: str
    level: str = "info"
    context: dict[str, Any] = field(default_factory=dict)
    entity_type: str | None = None
    entity_id: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    id: int = 0

