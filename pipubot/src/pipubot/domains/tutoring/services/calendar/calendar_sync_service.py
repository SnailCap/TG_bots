from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from core.db.transactional import transactional
from core.shared.utils.time_helpers import utcnow
from pipubot.domains.tutoring.models.enums import LessonStatus
from pipubot.domains.tutoring.repositories.calendar_source_repository import (
    get_calendar_source,
    set_last_synced_at,
    set_sync_token,
    upsert_calendar_source,
)
from pipubot.domains.tutoring.repositories.lesson_repository import upsert_lesson_from_gcal_event
from pipubot.domains.tutoring.services.calendar.student_title_match import resolve_student_id_by_event_title

from pipubot.domains.tutoring.integrations.google_calendar.calendar_client import (
    CalendarClient,
    CalendarEventsPage,
    CalendarSyncTokenExpired,
)


def _map_status(ev_status: str) -> LessonStatus:
    return LessonStatus.CANCELED if ev_status == "cancelled" else LessonStatus.PLANNED


async def _apply_events(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    calendar_id: str,
    page: CalendarEventsPage,
) -> None:
    for ev in page.items:
        safe_title = None if ev.status == "cancelled" else ev.summary
        safe_desc = None if ev.status == "cancelled" else ev.description

        res = await resolve_student_id_by_event_title(
            session,
            tutor_user_id=tutor_user_id,
            title=ev.summary,
        )
        student_id = res.student_id if res.kind == "matched" else None

        await upsert_lesson_from_gcal_event(
            session,
            tutor_user_id=tutor_user_id,
            google_calendar_id=calendar_id,
            google_event_id=ev.google_event_id,
            start_at=ev.start_at,
            end_at=ev.end_at,
            status=_map_status(ev.status),
            google_updated_at=ev.updated_at,
            google_ical_uid=ev.ical_uid,
            google_recurring_event_id=ev.recurring_event_id,
            title=safe_title,
            description=safe_desc,
            student_id=student_id,
        )


@transactional
async def sync_calendar_window(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    calendar_id: str,
    client: CalendarClient,
    horizon_days: int = 60,
    backfill_days: int = 7,
    now: datetime | None = None,
) -> None:
    now = now or utcnow()
    time_min = now - timedelta(days=backfill_days)
    time_max = now + timedelta(days=horizon_days)

    source = await upsert_calendar_source(session, tutor_user_id=tutor_user_id, calendar_id=calendar_id)
    source.window_days = horizon_days

    page = await client.list_events_window(
        calendar_id=calendar_id,
        time_min=time_min,
        time_max=time_max,
        show_deleted=True,
    )

    await _apply_events(session, tutor_user_id=tutor_user_id, calendar_id=calendar_id, page=page)

    await set_sync_token(session, tutor_user_id=tutor_user_id, calendar_id=calendar_id, sync_token=page.next_sync_token)
    await set_last_synced_at(session, tutor_user_id=tutor_user_id, calendar_id=calendar_id, last_synced_at=now)


@transactional
async def sync_calendar_delta(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    calendar_id: str,
    client: CalendarClient,
    now: datetime | None = None,
) -> None:
    now = now or utcnow()

    source = await get_calendar_source(session, tutor_user_id=tutor_user_id, calendar_id=calendar_id)
    if not source or not source.sync_token:
        return

    page = await client.list_events_delta(
        calendar_id=calendar_id,
        sync_token=source.sync_token,
        show_deleted=True,
    )

    await _apply_events(session, tutor_user_id=tutor_user_id, calendar_id=calendar_id, page=page)

    await set_sync_token(session, tutor_user_id=tutor_user_id, calendar_id=calendar_id, sync_token=page.next_sync_token)
    await set_last_synced_at(session, tutor_user_id=tutor_user_id, calendar_id=calendar_id, last_synced_at=now)


@transactional
async def sync_calendar(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    calendar_id: str,
    client: CalendarClient,
    horizon_days: int = 60,
    backfill_days: int = 7,
    now: datetime | None = None,
) -> None:
    """
    Единая точка входа для периодического запуска:

    - нет sync_token -> window sync
    - есть sync_token -> delta sync
    - если sync_token протух (410 Gone) -> window sync заново
    """
    now = now or utcnow()

    source = await get_calendar_source(session, tutor_user_id=tutor_user_id, calendar_id=calendar_id)
    if not source or not source.sync_token:
        await sync_calendar_window(
            session,
            tutor_user_id=tutor_user_id,
            calendar_id=calendar_id,
            client=client,
            horizon_days=horizon_days,
            backfill_days=backfill_days,
            now=now,
        )
        return

    try:
        await sync_calendar_delta(
            session,
            tutor_user_id=tutor_user_id,
            calendar_id=calendar_id,
            client=client,
            now=now,
        )
    except CalendarSyncTokenExpired:
        await sync_calendar_window(
            session,
            tutor_user_id=tutor_user_id,
            calendar_id=calendar_id,
            client=client,
            horizon_days=horizon_days,
            backfill_days=backfill_days,
            now=now,
        )