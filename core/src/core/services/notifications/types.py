from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class NotificationSource:
    type: str
    id: int