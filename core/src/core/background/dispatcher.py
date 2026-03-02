from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from core.background.errors import NonRetryableTaskError, UnknownTaskTypeError
from core.db.models.background_task import BackgroundTask
from core.enums.background_task_enums import BackgroundTaskType
from core.runtime.app_services import AppServices

Handler = Callable[[AsyncSession, dict[str, Any]], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class DefaultTaskDispatcher:
    handlers: Mapping[BackgroundTaskType, Handler]
    services: AppServices

    async def dispatch(self, session: AsyncSession, task: BackgroundTask) -> None:
        task_type: BackgroundTaskType = BackgroundTaskType(str(task.task_type))
        handler = self.handlers.get(task_type)
        if handler is None:
            raise UnknownTaskTypeError(f"No handler registered for task_type={task_type}")

        payload = task.payload
        if not isinstance(payload, dict):
            raise NonRetryableTaskError(f"Task payload must be dict, got {type(payload)}")

        await handler(session, payload)
