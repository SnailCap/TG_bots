from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from pipubot.domains.tutoring.integrations.google_calendar.dto import (
    CalendarEventDTO,
    CalendarEventsPage,
)


@dataclass(frozen=True, slots=True)
class AccessToken:
    token: str


class AccessTokenProvider(Protocol):
    async def get_access_token(self) -> AccessToken:
        """
        Return a valid Bearer token.
        """
        ...


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

    async def get_event(
        self,
        *,
        calendar_id: str,
        event_id: str,
    ) -> CalendarEventDTO: ...

    async def ensure_event_meet_link(
        self,
        *,
        calendar_id: str,
        event_id: str,
    ) -> str: ...