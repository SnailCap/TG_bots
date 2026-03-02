from __future__ import annotations

from enum import StrEnum
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


def _key(task_type: str | StrEnum) -> BackgroundTaskType:
    # BackgroundTaskType is a str alias, so this is fine
    return BackgroundTaskType(str(task_type))


def task_handler(task_type: str | StrEnum) -> Callable[[TaskHandler], TaskHandler]:
    key = _key(task_type)

    def _decorator(fn: TaskHandler) -> TaskHandler:
        existing = _REGISTRY.get(key)
        if existing is not None and existing is not fn:
            raise DuplicateTaskHandlerError(
                f"Handler already registered for task type: {key}"
            )
        _REGISTRY[key] = fn
        return fn

    return _decorator


def build_task_handlers() -> dict[BackgroundTaskType, TaskHandler]:
    return dict(_REGISTRY)


def get_task_handler(task_type: str | StrEnum) -> TaskHandler:
    key = _key(task_type)
    try:
        return _REGISTRY[key]
    except KeyError as e:
        raise UnknownTaskTypeError(f"Unknown task type: {key}") from e