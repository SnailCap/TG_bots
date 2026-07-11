from __future__ import annotations

from datetime import datetime

from app.domain.enums import RuntimeState
from app.domain.runtime import BotRuntimeStatus, RuntimeHistoryEntry

from .common import ApiModel
from .projects import BotIdentityResponse


class RuntimeStatusResponse(ApiModel):
    state: RuntimeState
    project_id: str
    telegram_connected: bool
    bot_identity: BotIdentityResponse | None = None
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    last_error: str | None = None


class RuntimeLogResponse(ApiModel):
    id: int | None
    project_id: str
    session_id: str | None
    event_type: str
    source: str
    level: str
    message: str
    context: dict
    created_at: datetime


def runtime_status_response(value: BotRuntimeStatus) -> RuntimeStatusResponse:
    identity = value.bot_identity
    return RuntimeStatusResponse(
        state=value.state,
        project_id=value.project_id or "",
        telegram_connected=value.state is RuntimeState.RUNNING,
        bot_identity=(
            BotIdentityResponse(
                bot_id=identity.bot_id,
                username=identity.username,
                display_name=identity.display_name,
            )
            if identity is not None
            else None
        ),
        started_at=value.started_at,
        stopped_at=value.stopped_at,
        last_error=value.last_error,
    )


def runtime_log_response(value: RuntimeHistoryEntry) -> RuntimeLogResponse:
    return RuntimeLogResponse(
        id=value.id,
        project_id=value.project_id,
        session_id=value.session_id,
        event_type=value.event_type,
        source=value.event_type,
        level=value.level,
        message=value.message,
        context=dict(value.context),
        created_at=value.created_at,
    )
