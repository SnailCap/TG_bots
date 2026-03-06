from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from core.background.errors import NonRetryableTaskError, UnknownTaskTypeError
from core.background.handler_registry import HandlerEntry, TaskType
from core.db.models.background_task import BackgroundTask
from core.runtime.app_services import AppServices

Handler = Callable[[AsyncSession, dict[str, Any], AppServices], Awaitable[None]]


class ForbiddenTaskInvocationError(NonRetryableTaskError):
    pass


@dataclass(frozen=True, slots=True)
class DefaultTaskDispatcher:
    handler_entries: dict[TaskType, HandlerEntry]
    services: AppServices

    async def dispatch(self, session: AsyncSession, task: BackgroundTask) -> None:
        task_type: str = str(task.task_type)
        entry = self.handler_entries.get(task_type)
        if entry is None:
            raise UnknownTaskTypeError(f"No handler registered for task_type={task_type}")

        if entry.only_recurring and task.recurring_task_id is None:
            raise ForbiddenTaskInvocationError(
                f"Task {task_type} is only allowed from recurring context"
            )

        payload = task.payload
        if not isinstance(payload, dict):
            raise NonRetryableTaskError(f"Task payload must be dict, got {type(payload)}")

        await entry.fn(session, payload, self.services)