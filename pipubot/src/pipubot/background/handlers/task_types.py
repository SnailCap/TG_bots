from __future__ import annotations

from enum import StrEnum, auto


class BackgroundTaskType(StrEnum):
    SYNC_GCAL = auto()