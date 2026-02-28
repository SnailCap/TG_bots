# core/src/background/dispatcher.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models.background_task import BackgroundTask
from core.enums.background_task_enums import BackgroundTaskType

Handler = Callable[[AsyncSession, dict[str, Any]], Awaitable[None]]


class UnknownTaskTypeError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class DefaultTaskDispatcher:
    handlers: dict[BackgroundTaskType, Handler]

    async def dispatch(self, session: AsyncSession, task: BackgroundTask) -> None:
        handler = self.handlers.get(task.task_type)
        if handler is None:
            raise UnknownTaskTypeError(f"No handler registered for task_type={task.task_type}")

        payload = task.payload or {}
        if not isinstance(payload, dict):
            raise TypeError(f"Task payload must be dict, got {type(payload)}")

        await handler(session, payload)