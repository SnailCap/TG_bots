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
    """
    Google returns RFC3339 strings, often with 'Z'.
    datetime.fromisoformat doesn't accept 'Z', so we normalize.
    """
    if dt.endswith("Z"):
        dt = dt[:-1] + "+00:00"
    return datetime.fromisoformat(dt)


def _parse_event_time(obj: dict[str, Any], *, prefer_tz: str | None = None) -> datetime:
    """
    Google event time can be:
    - {"dateTime": "...", "timeZone": "..."} (timed)
    - {"date": "YYYY-MM-DD"} (all-day)
    """
    if "dateTime" in obj and obj["dateTime"]:
        return _parse_rfc3339(obj["dateTime"])

    # all-day: treat as midnight in UTC (or could use prefer_tz later)
    # If you want local timezone correctness for all-day events, we can refine.
    d = obj.get("date")
    if not d:
        raise CalendarClientError("Event time missing date/dateTime")
    return datetime.fromisoformat(d).replace(tzinfo=timezone.utc)


def _extract_meet_url(ev: dict[str, Any]) -> str | None:
    # Most common: hangoutLink or conferenceData entryPoints
    hangout = ev.get("hangoutLink")
    if hangout:
        return hangout

    conf = ev.get("conferenceData") or {}
    eps = conf.get("entryPoints") or []
    for ep in eps:
        if ep.get("entryPointType") in ("video", "more"):
            uri = ep.get("uri")
            if uri:
                return uri
    return None


@dataclass(frozen=True)
class GoogleCalendarClientConfig:
    access_token: str
    timeout_s: float = 20.0
    base_url: str = "https://www.googleapis.com/calendar/v3"


class GoogleCalendarClient:
    """
    Minimal async client for Google Calendar API v3 (events.list).

    Auth:
        Pass an OAuth2 access token (Bearer).
        Later you can replace it with refresh logic (see google_oauth.py skeleton).
    """

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
            # optional: "maxResults": 2500,
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

    async def _events_list(self, *, calendar_id: str, params: dict[str, str]) -> CalendarEventsPage:
        url = f"{self._cfg.base_url}/calendars/{calendar_id}/events"
        headers = {"Authorization": f"Bearer {self._cfg.access_token}"}

        items: list[CalendarEventDTO] = []
        next_sync_token: str | None = None

        async with httpx.AsyncClient(timeout=self._cfg.timeout_s) as client:
            page_token: str | None = None

            while True:
                p = dict(params)
                if page_token:
                    p["pageToken"] = page_token

                resp = await client.get(url, headers=headers, params=p)
                if resp.status_code == 410:
                    raise CalendarSyncTokenExpired("Google Calendar sync token expired (410 Gone)")
                if resp.status_code in (401, 403):
                    raise CalendarAuthError(f"Google Calendar auth error: {resp.status_code} {resp.text}")
                if resp.status_code == 429:
                    raise CalendarRateLimitError(f"Google Calendar rate limited: {resp.text}")
                if resp.status_code >= 400:
                    raise CalendarClientError(f"Google Calendar error: {resp.status_code} {resp.text}")

                data = resp.json()

                for ev in data.get("items", []):
                    # If cancelled and showDeleted=true, Google may omit start/end sometimes.
                    # We'll skip those we can't materialize.
                    try:
                        start_at = _parse_event_time(ev.get("start", {}))
                        end_at = _parse_event_time(ev.get("end", {}))
                    except Exception:
                        continue

                    items.append(
                        CalendarEventDTO(
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
                    )

                page_token = data.get("nextPageToken")
                next_sync_token = data.get("nextSyncToken") or next_sync_token

                if not page_token:
                    break

        return CalendarEventsPage(items=items, next_sync_token=next_sync_token)