from __future__ import annotations

from typing import Any, Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from core.enums.background_task_enums import BackgroundTaskType

TaskPayload = dict[str, Any]
TaskHandler = Callable[[AsyncSession, TaskPayload], Awaitable[None]]

_REGISTRY: dict[BackgroundTaskType, TaskHandler] = {}


class DuplicateTaskHandlerError(RuntimeError):
    pass


class UnknownTaskTypeError(RuntimeError):
    pass


def task_handler(task_type: BackgroundTaskType) -> Callable[[TaskHandler], TaskHandler]:
    def _decorator(fn: TaskHandler) -> TaskHandler:
        existing = _REGISTRY.get(task_type)
        if existing is not None and existing is not fn:
            raise DuplicateTaskHandlerError(
                f"Handler already registered for task type: {task_type}"
            )
        _REGISTRY[task_type] = fn
        return fn

    return _decorator


def build_task_handlers() -> dict[BackgroundTaskType, TaskHandler]:
    return dict(_REGISTRY)


def get_task_handler(task_type: BackgroundTaskType) -> TaskHandler:
    try:
        return _REGISTRY[task_type]
    except KeyError as e:
        raise UnknownTaskTypeError(f"Unknown task type: {task_type}") from e