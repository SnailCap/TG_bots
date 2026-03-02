from __future__ import annotations

from enum import StrEnum, auto


class BackgroundTaskType(StrEnum):
    SEND_NOTIFICATION = auto()
    PRINT_HELLO = auto()