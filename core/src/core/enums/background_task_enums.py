from __future__ import annotations

from enum import StrEnum, auto


class BackgroundTaskStatus(StrEnum):
    PENDING = auto()
    PROCESSING = auto()
    DONE = auto()
    FAILED = auto()
    CANCELED = auto()


class BackgroundTaskType(StrEnum):
    SEND_NOTIFICATION = auto()

class RecurringTaskStatus(StrEnum):
    ACTIVE = auto()     # планировщик создаёт новые BackgroundTask
    PROCESSING = auto()
    PAUSED = auto()     # временно выключена, но не удалена
    DISABLED = auto() # полностью отключена, можно считать "архивной"