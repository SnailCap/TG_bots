from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Awaitable, Callable, Optional, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from core.background.enums import RecurringTaskStatus
from core.runtime.app_services import AppServices

TaskPayload = dict[str, Any]

TaskHandler = Callable[
    [AsyncSession, TaskPayload, AppServices],
    Awaitable[None],
]

TTaskHandler = TypeVar("TTaskHandler", bound=TaskHandler)


class DuplicateTaskHandlerError(RuntimeError):
    pass


class UnknownTaskTypeError(RuntimeError):
    pass


class DuplicateRecurringSpecError(RuntimeError):
    pass


# теперь task_type — обычная строка
TaskType = str


@dataclass(frozen=True, slots=True)
class HandlerEntry:
    task_type: TaskType
    fn: TaskHandler
    only_recurring: bool = False


@dataclass(frozen=True, slots=True)
class RecurringSpec:
    key: str
    task_type: TaskType
    interval_seconds: int
    payload_template: Optional[dict[str, Any]] = None
    max_runs: Optional[int] = None
    status: RecurringTaskStatus = RecurringTaskStatus.ACTIVE


_HANDLERS: dict[TaskType, HandlerEntry] = {}
_RECURRING_SPECS: dict[str, RecurringSpec] = {}  # key -> spec (unique)


def _key(task_type: str | StrEnum) -> TaskType:
    return str(task_type)


def background_task_handler(
    task_type: str | StrEnum | None = None,
    *,
    # --- recurring options (optional) ---
    recurring_key: str | None = None,
    recurring_interval_seconds: int | None = None,
    recurring_payload_template: dict[str, Any] | None = None,
    recurring_max_runs: int | None = None,
    recurring_status: RecurringTaskStatus = RecurringTaskStatus.ACTIVE,
    # --- execution policy ---
    only_recurring: bool = False,
    # --- defaults for autogen ---
    default_recurring_prefix: str = "system.",
) -> Callable[[TTaskHandler], TTaskHandler]:
    """
    Registers task handler for task_type.
    If task_type is omitted, it is derived from fn.__name__.

    Recurring behavior:
    - If recurring_interval_seconds is None -> no recurring spec is registered.
    - If recurring_interval_seconds is provided and recurring_key is None ->
      recurring_key is auto-generated as f"{default_recurring_prefix}{task_type}".
    - If recurring_key is provided but recurring_interval_seconds is None -> ValueError.
    """
    def _decorator(fn: TTaskHandler) -> TTaskHandler:
        resolved_type = _key(task_type if task_type is not None else fn.__name__)

        existing = _HANDLERS.get(resolved_type)
        if existing is not None and existing.fn is not fn:
            raise DuplicateTaskHandlerError(f"Handler already registered for task type: {resolved_type}")

        _HANDLERS[resolved_type] = HandlerEntry(task_type=resolved_type, fn=fn, only_recurring=only_recurring)

        # recurring
        if recurring_key is not None and recurring_interval_seconds is None:
            raise ValueError("recurring_interval_seconds must be provided when recurring_key is set")

        if recurring_interval_seconds is not None:
            resolved_recurring_key = recurring_key or f"{default_recurring_prefix}{resolved_type}"

            spec = RecurringSpec(
                key=resolved_recurring_key,
                task_type=resolved_type,
                interval_seconds=recurring_interval_seconds,
                payload_template=recurring_payload_template,
                max_runs=recurring_max_runs,
                status=recurring_status,
            )

            prev = _RECURRING_SPECS.get(resolved_recurring_key)
            if prev is not None and prev != spec:
                raise DuplicateRecurringSpecError(f"Recurring spec key already registered: {resolved_recurring_key}")

            _RECURRING_SPECS[resolved_recurring_key] = spec

        return fn

    return _decorator


# -------------------------
# Compatibility API
# -------------------------

def build_task_handlers() -> dict[TaskType, TaskHandler]:
    return {k: v.fn for k, v in _HANDLERS.items()}


def get_task_handler(task_type: str | StrEnum) -> TaskHandler:
    key = _key(task_type)
    try:
        return _HANDLERS[key].fn
    except KeyError as e:
        raise UnknownTaskTypeError(f"Unknown task type: {key}") from e


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


def build_handler_entries() -> dict[TaskType, HandlerEntry]:
    return dict(_HANDLERS.items())