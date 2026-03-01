from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


# ----------------------------
# DTO
# ----------------------------

@dataclass(frozen=True)
class CalendarEventDTO:
    """
    Represents a single *instance* of an event as returned by Google Calendar
    when using events.list with singleEvents=true.

    google_event_id:
        Google event id (for instances too).
    status:
        "confirmed" | "cancelled" | "tentative" (we treat non-cancelled as planned by default)
    updated_at:
        Google 'updated' field parsed to datetime (may be None)
    """
    google_event_id: str
    status: str
    summary: str | None
    description: str | None
    start_at: datetime
    end_at: datetime
    updated_at: datetime | None
    ical_uid: str | None = None
    recurring_event_id: str | None = None
    meeting_url: str | None = None


@dataclass(frozen=True)
class CalendarEventsPage:
    """
    For Google Calendar sync:

    - next_sync_token is returned at the end of a full list/delta call
      and must be stored for future deltas.
    """
    items: list[CalendarEventDTO]
    next_sync_token: str | None


# ----------------------------
# Errors
# ----------------------------

class CalendarClientError(RuntimeError):
    pass


class CalendarAuthError(CalendarClientError):
    """401/403 typically."""
    pass


class CalendarSyncTokenExpired(CalendarClientError):
    """
    Google returns 410 Gone when syncToken is invalid/expired.

    Your sync service should catch it and fall back to window sync.
    """
    pass


class CalendarRateLimitError(CalendarClientError):
    """429 or quota limit responses."""
    pass


# ----------------------------
# Client protocol
# ----------------------------

class CalendarClient(Protocol):
    async def list_events_window(
        self,
        *,
        calendar_id: str,
        time_min: datetime,
        time_max: datetime,
        show_deleted: bool = True,
    ) -> CalendarEventsPage: ...

    async def list_events_delta(
        self,
        *,
        calendar_id: str,
        sync_token: str,
        show_deleted: bool = True,
    ) -> CalendarEventsPage: ...