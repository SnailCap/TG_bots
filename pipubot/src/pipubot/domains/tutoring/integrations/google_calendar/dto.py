from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CalendarEventDTO:
    """
    Represents a single event instance returned by Google Calendar
    when using events.list with singleEvents=true.
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
    meet_url: str | None = None


@dataclass(frozen=True, slots=True)
class CalendarEventsPage:
    """
    Google Calendar sync page.

    next_sync_token is returned by Google after full/delta sync and should be
    stored for future incremental sync calls.
    """

    items: tuple[CalendarEventDTO, ...]
    next_sync_token: str | None