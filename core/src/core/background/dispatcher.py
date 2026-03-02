from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from core.background.errors import NonRetryableTaskError
from core.db.models.background_task import BackgroundTask
from core.enums.background_task_enums import BackgroundTaskType

Handler = Callable[[AsyncSession, dict[str, Any]], Awaitable[None]]


class UnknownTaskTypeError(NonRetryableTaskError):
    """No handler registered for task.task_type."""


@dataclass(frozen=True, slots=True)
class DefaultTaskDispatcher:
    handlers: Mapping[BackgroundTaskType, Handler]

    async def dispatch(self, session: AsyncSession, task: BackgroundTask) -> None:
        handler = self.handlers.get(task.task_type)
        if handler is None:
            raise UnknownTaskTypeError(f"No handler registered for task_type={task.task_type}")

        payload = task.payload
        if not isinstance(payload, dict):
            raise NonRetryableTaskError(f"Task payload must be dict, got {type(payload)}")

        await handler(session, payload)