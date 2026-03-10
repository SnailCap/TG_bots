from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from .dto import (
    CalendarEventDTO,
    CalendarEventsPage,
)
from .errors import (
    CalendarAuthError,
    CalendarClientError,
    CalendarEventNotFoundError,
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

    date_value = obj.get("date")
    if not date_value:
        raise CalendarClientError("Event time missing date/dateTime")

    return datetime.fromisoformat(date_value).replace(tzinfo=timezone.utc)


def _extract_meet_url(ev: dict[str, Any]) -> str | None:
    hangout = ev.get("hangoutLink")
    if isinstance(hangout, str) and hangout.strip():
        return hangout.strip()

    conf = ev.get("conferenceData") or {}
    for ep in (conf.get("entryPoints") or []):
        if not isinstance(ep, dict):
            continue

        if ep.get("entryPointType") not in ("video", "more"):
            continue

        uri = ep.get("uri")
        if isinstance(uri, str) and uri.strip():
            return uri.strip()

    return None


def _raise_for_google_calendar_response(resp: httpx.Response) -> None:
    code = resp.status_code

    if code == 404:
        raise CalendarEventNotFoundError("Google Calendar event not found.")
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
    Returns None for events we can't materialize
    (for example, malformed canceled events without valid start/end).
    """
    try:
        start_at = _parse_event_time(ev.get("start", {}))
        end_at = _parse_event_time(ev.get("end", {}))
    except Exception:
        return None

    google_event_id = ev.get("id")
    if not isinstance(google_event_id, str) or not google_event_id.strip():
        return None

    status = ev.get("status", "confirmed")
    if not isinstance(status, str) or not status.strip():
        status = "confirmed"

    summary = ev.get("summary")
    if not isinstance(summary, str):
        summary = None

    description = ev.get("description")
    if not isinstance(description, str):
        description = None

    updated_at: datetime | None = None
    updated_raw = ev.get("updated")
    if isinstance(updated_raw, str) and updated_raw.strip():
        updated_at = _parse_rfc3339(updated_raw)

    ical_uid = ev.get("iCalUID")
    if not isinstance(ical_uid, str):
        ical_uid = None

    recurring_event_id = ev.get("recurringEventId")
    if not isinstance(recurring_event_id, str):
        recurring_event_id = None

    return CalendarEventDTO(
        google_event_id=google_event_id.strip(),
        status=status.strip(),
        summary=summary.strip() if isinstance(summary, str) and summary.strip() else None,
        description=description.strip() if isinstance(description, str) and description.strip() else None,
        start_at=start_at,
        end_at=end_at,
        updated_at=updated_at,
        ical_uid=ical_uid.strip() if isinstance(ical_uid, str) and ical_uid.strip() else None,
        recurring_event_id=(
            recurring_event_id.strip()
            if isinstance(recurring_event_id, str) and recurring_event_id.strip()
            else None
        ),
        meet_url=_extract_meet_url(ev),
    )


def _parse_items(data: dict[str, Any]) -> tuple[CalendarEventDTO, ...]:
    out: list[CalendarEventDTO] = []

    for ev in data.get("items", []):
        if not isinstance(ev, dict):
            continue

        dto = _try_parse_calendar_event(ev)
        if dto is not None:
            out.append(dto)

    return tuple(out)


def _build_meet_request_id(*, calendar_id: str, event_id: str) -> str:
    raw = f"{calendar_id}:{event_id}:meet"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
    return f"meet-{digest}"


@dataclass(frozen=True, slots=True)
class GoogleCalendarClientConfig:
    access_token: str
    timeout_s: float = 20.0
    base_url: str = "https://www.googleapis.com/calendar/v3"

    meet_poll_attempts: int = 5
    meet_poll_delay_s: float = 1.0


class GoogleCalendarClient:
    def __init__(self, config: GoogleCalendarClientConfig):
        self._cfg = config

    def _build_events_url(self, *, calendar_id: str) -> str:
        return f"{self._cfg.base_url}/calendars/{calendar_id}/events"

    def _build_event_url(self, *, calendar_id: str, event_id: str) -> str:
        return f"{self._cfg.base_url}/calendars/{calendar_id}/events/{event_id}"

    def _build_auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._cfg.access_token}"}

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
            "conferenceDataVersion": "1",
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
            "conferenceDataVersion": "1",
        }
        return await self._events_list(calendar_id=calendar_id, params=params)

    async def get_event(
        self,
        *,
        calendar_id: str,
        event_id: str,
    ) -> CalendarEventDTO:
        url = self._build_event_url(calendar_id=calendar_id, event_id=event_id)
        headers = self._build_auth_headers()
        params = {"conferenceDataVersion": "1"}

        async with httpx.AsyncClient(timeout=self._cfg.timeout_s) as client:
            resp = await client.get(url, headers=headers, params=params)

        _raise_for_google_calendar_response(resp)

        data = resp.json()
        if not isinstance(data, dict):
            raise CalendarClientError("Google Calendar returned invalid event payload.")

        dto = _try_parse_calendar_event(data)
        if dto is None:
            raise CalendarClientError("Google Calendar event payload could not be parsed.")

        return dto

    async def ensure_event_meet_link(
        self,
        *,
        calendar_id: str,
        event_id: str,
    ) -> str:
        event = await self.get_event(
            calendar_id=calendar_id,
            event_id=event_id,
        )
        if event.meet_url:
            return event.meet_url

        await self._request_event_meet_link_creation(
            calendar_id=calendar_id,
            event_id=event_id,
        )

        return await self._poll_event_meet_link(
            calendar_id=calendar_id,
            event_id=event_id,
        )

    async def _request_event_meet_link_creation(
        self,
        *,
        calendar_id: str,
        event_id: str,
    ) -> None:
        url = self._build_event_url(calendar_id=calendar_id, event_id=event_id)
        headers = self._build_auth_headers()
        params = {"conferenceDataVersion": "1"}
        body = {
            "conferenceData": {
                "createRequest": {
                    "requestId": _build_meet_request_id(
                        calendar_id=calendar_id,
                        event_id=event_id,
                    ),
                    "conferenceSolutionKey": {
                        "type": "hangoutsMeet",
                    },
                }
            }
        }

        async with httpx.AsyncClient(timeout=self._cfg.timeout_s) as client:
            resp = await client.patch(
                url,
                headers=headers,
                params=params,
                json=body,
            )

        _raise_for_google_calendar_response(resp)

        data = resp.json()
        if not isinstance(data, dict):
            raise CalendarClientError(
                "Google Calendar returned invalid patched event payload."
            )

    async def _poll_event_meet_link(
        self,
        *,
        calendar_id: str,
        event_id: str,
    ) -> str:
        attempts = max(1, self._cfg.meet_poll_attempts)

        for attempt in range(attempts):
            event = await self.get_event(
                calendar_id=calendar_id,
                event_id=event_id,
            )
            if event.meet_url:
                return event.meet_url

            if attempt < attempts - 1:
                await asyncio.sleep(self._cfg.meet_poll_delay_s)

        raise CalendarClientError(
            "Google Calendar accepted Meet creation request, "
            "but Meet link was not ready after polling."
        )

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

    async def _events_list(
        self,
        *,
        calendar_id: str,
        params: dict[str, str],
    ) -> CalendarEventsPage:
        url = self._build_events_url(calendar_id=calendar_id)
        headers = self._build_auth_headers()

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

        return CalendarEventsPage(
            items=tuple(items),
            next_sync_token=next_sync_token,
        )