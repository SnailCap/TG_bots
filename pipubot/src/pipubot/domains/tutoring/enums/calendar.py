from __future__ import annotations

from enum import StrEnum


class CalendarSourceStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    REAUTH_REQUIRED = "reauth_required"
