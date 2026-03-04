from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Awaitable, Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from core.enums.background_task_enums import BackgroundTaskType, RecurringTaskStatus
from core.runtime.app_services import AppServices

TaskPayload = dict[str, Any]
TaskHandler = Callable[
    [AsyncSession, TaskPayload, AppServices],
    Awaitable[None],
]


class DuplicateTaskHandlerError(RuntimeError):
    pass


class UnknownTaskTypeError(RuntimeError):
    pass


class DuplicateRecurringSpecError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class HandlerEntry:
    task_type: BackgroundTaskType
    fn: TaskHandler
    only_recurring: bool = False


@dataclass(frozen=True, slots=True)
class RecurringSpec:
    key: str
    task_type: BackgroundTaskType
    interval_seconds: int
    payload_template: Optional[dict[str, Any]] = None
    max_runs: Optional[int] = None
    status: RecurringTaskStatus = RecurringTaskStatus.ACTIVE


_HANDLERS: dict[BackgroundTaskType, HandlerEntry] = {}
_RECURRING_SPECS: dict[str, RecurringSpec] = {}  # key -> spec (unique)


def _key(task_type: str | StrEnum) -> BackgroundTaskType:
    # BackgroundTaskType is a StrEnum (string-like), so this is fine
    return BackgroundTaskType(str(task_type))


def task_handler(
    task_type: str | StrEnum,
    *,
    # --- recurring options (optional) ---
    recurring_key: str | None = None,
    recurring_interval_seconds: int | None = None,
    recurring_payload_template: dict[str, Any] | None = None,
    recurring_max_runs: int | None = None,
    recurring_status: RecurringTaskStatus = RecurringTaskStatus.ACTIVE,
    # --- execution policy ---
    only_recurring: bool = False,
) -> Callable[[TaskHandler], TaskHandler]:
    """
    Registers task handler for task_type.
    Optionally registers a recurring spec that points to the same task_type.

    Backward-compatible: you can still call @task_handler("X") with only one arg.
    """
    key = _key(task_type)

    # validate recurring params consistency
    if (recurring_key is None) ^ (recurring_interval_seconds is None):
        raise ValueError("recurring_key and recurring_interval_seconds must be provided together")

    def _decorator(fn: TaskHandler) -> TaskHandler:
        existing = _HANDLERS.get(key)
        if existing is not None and existing.fn is not fn:
            raise DuplicateTaskHandlerError(f"Handler already registered for task type: {key}")

        _HANDLERS[key] = HandlerEntry(task_type=key, fn=fn, only_recurring=only_recurring)

        if recurring_key is not None and recurring_interval_seconds is not None:
            spec = RecurringSpec(
                key=recurring_key,
                task_type=key,
                interval_seconds=recurring_interval_seconds,
                payload_template=recurring_payload_template,
                max_runs=recurring_max_runs,
                status=recurring_status,
            )
            prev = _RECURRING_SPECS.get(recurring_key)
            if prev is not None and prev != spec:
                raise DuplicateRecurringSpecError(f"Recurring spec key already registered: {recurring_key}")
            _RECURRING_SPECS[recurring_key] = spec

        return fn

    return _decorator


# -------------------------
# Compatibility API (unchanged behavior)
# -------------------------

def build_task_handlers() -> dict[BackgroundTaskType, TaskHandler]:
    # kept exactly as before: task_type -> handler fn
    return {k: v.fn for k, v in _HANDLERS.items()}


def get_task_handler(task_type: str | StrEnum) -> TaskHandler:
    key = _key(task_type)
    try:
        return _HANDLERS[key].fn
    except KeyError as e:
        raise UnknownTaskTypeError(f"Unknown task type: {key}") from e


# -------------------------
# New API (for recurring bootstrap & policy checks)
# -------------------------

def get_handler_entry(task_type: str | StrEnum) -> HandlerEntry:
    key = _key(task_type)
    try:
        return _HANDLERS[key]
    except KeyError as e:
        raise UnknownTaskTypeError(f"Unknown task type: {key}") from e


def get_recurring_specs(*, prefix: str | None = None) -> list[RecurringSpec]:
    specs = list(_RECURRING_SPECS.values())
    if prefix is None:
        return specs
    return [s for s in specs if s.key.startswith(prefix)]

def build_handler_entries() -> dict[BackgroundTaskType, HandlerEntry]:
    return dict(_HANDLERS)