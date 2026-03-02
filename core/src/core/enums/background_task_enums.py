from __future__ import annotations

from enum import StrEnum, auto
from typing import TypeAlias

BackgroundTaskType: TypeAlias = str


class BackgroundTaskStatus(StrEnum):
    PENDING = auto()
    PROCESSING = auto()
    DONE = auto()
    FAILED = auto()
    CANCELED = auto()


class RecurringTaskStatus(StrEnum):
    ACTIVE = auto()
    PROCESSING = auto()
    PAUSED = auto()
    DISABLED = auto()
