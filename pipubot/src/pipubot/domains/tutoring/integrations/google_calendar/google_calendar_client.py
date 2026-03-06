from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from pipubot.domains.tutoring.integrations.google_calendar.calendar_client import (
    CalendarAuthError,
    CalendarClientError,
    CalendarEventsPage,
    CalendarEventDTO,
    CalendarRateLimitError,
    CalendarSyncTokenExpired,
)


def _parse_rfc3339(dt: str) -> datetime:
    if dt.endswith("Z"):
        dt = dt[:-1] + "+00:00"
    return datetime.fromisoformat(dt)


def _parse_event_time(obj: dict[str, Any]) -> datetime:
    if obj.get("dateTime"):
        return _parse_rfc3339(obj["dateTime"])

    d = obj.get("date")
    if not d:
        raise CalendarClientError("Event time missing date/dateTime")
    return datetime.fromisoformat(d).replace(tzinfo=timezone.utc)


def _extract_meet_url(ev: dict[str, Any]) -> str | None:
    hangout = ev.get("hangoutLink")
    if hangout:
        return hangout

    conf = ev.get("conferenceData") or {}
    for ep in (conf.get("entryPoints") or []):
        if ep.get("entryPointType") in ("video", "more"):
            uri = ep.get("uri")
            if uri:
                return uri
    return None


def _raise_for_google_calendar_response(resp: httpx.Response) -> None:
    code = resp.status_code
    if code == 410:
        raise CalendarSyncTokenExpired("Google Calendar sync token expired (410 Gone)")
    if code in (401, 403):
        raise CalendarAuthError(f"Google Calendar auth error: {code} {resp.text}")
    if code == 429:
        raise CalendarRateLimitError(f"Google Calendar rate limited: {resp.text}")
    if code >= 400:
        raise CalendarClientError(f"Google Calendar error: {code} {resp.text}")


def _try_parse_calendar_event(ev: dict[str, Any]) -> CalendarEventDTO | None:
    """
    Returns None for events we can't materialize (e.g., canceled with missing start/end).
    """
    try:
        start_at = _parse_event_time(ev.get("start", {}))
        end_at = _parse_event_time(ev.get("end", {}))
    except Exception:
        return None

    return CalendarEventDTO(
        google_event_id=ev["id"],
        status=ev.get("status", "confirmed"),
        summary=ev.get("summary"),
        description=ev.get("description"),
        start_at=start_at,
        end_at=end_at,
        updated_at=_parse_rfc3339(ev["updated"]) if ev.get("updated") else None,
        ical_uid=ev.get("iCalUID"),
        recurring_event_id=ev.get("recurringEventId"),
        meeting_url=_extract_meet_url(ev),
    )


def _parse_items(data: dict[str, Any]) -> list[CalendarEventDTO]:
    out: list[CalendarEventDTO] = []
    for ev in data.get("items", []):
        dto = _try_parse_calendar_event(ev)
        if dto is not None:
            out.append(dto)
    return out


@dataclass(frozen=True)
class GoogleCalendarClientConfig:
    access_token: str
    timeout_s: float = 20.0
    base_url: str = "https://www.googleapis.com/calendar/v3"


class GoogleCalendarClient:
    def __init__(self, config: GoogleCalendarClientConfig):
        self._cfg = config

    async def list_events_window(
        self,
        *,
        calendar_id: str,
        time_min: datetime,
        time_max: datetime,
        show_deleted: bool = True,
    ) -> CalendarEventsPage:
        params = {
            "singleEvents": "true",
            "showDeleted": "true" if show_deleted else "false",
            "orderBy": "startTime",
            "timeMin": time_min.astimezone(timezone.utc).isoformat(),
            "timeMax": time_max.astimezone(timezone.utc).isoformat(),
        }
        return await self._events_list(calendar_id=calendar_id, params=params)

    async def list_events_delta(
        self,
        *,
        calendar_id: str,
        sync_token: str,
        show_deleted: bool = True,
    ) -> CalendarEventsPage:
        params = {
            "syncToken": sync_token,
            "showDeleted": "true" if show_deleted else "false",
        }
        return await self._events_list(calendar_id=calendar_id, params=params)

    async def _fetch_events_page(
        self,
        client: httpx.AsyncClient,
        *,
        url: str,
        headers: dict[str, str],
        base_params: dict[str, str],
        page_token: str | None,
    ) -> dict[str, Any]:
        params = dict(base_params)
        if page_token:
            params["pageToken"] = page_token

        resp = await client.get(url, headers=headers, params=params)
        _raise_for_google_calendar_response(resp)
        return resp.json()

    async def _events_list(self, *, calendar_id: str, params: dict[str, str]) -> CalendarEventsPage:
        url = f"{self._cfg.base_url}/calendars/{calendar_id}/events"
        headers = {"Authorization": f"Bearer {self._cfg.access_token}"}

        items: list[CalendarEventDTO] = []
        next_sync_token: str | None = None
        page_token: str | None = None

        async with httpx.AsyncClient(timeout=self._cfg.timeout_s) as client:
            while True:
                data = await self._fetch_events_page(
                    client,
                    url=url,
                    headers=headers,
                    base_params=params,
                    page_token=page_token,
                )

                items.extend(_parse_items(data))
                next_sync_token = data.get("nextSyncToken") or next_sync_token
                page_token = data.get("nextPageToken")

                if not page_token:
                    break

        return CalendarEventsPage(items=items, next_sync_token=next_sync_token)