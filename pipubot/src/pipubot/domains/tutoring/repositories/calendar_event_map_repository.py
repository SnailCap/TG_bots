from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pipubot.domains.tutoring.models.calendar_event_map import TutoringCalendarEventMap


async def get_event_map(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    calendar_id: str,
    google_event_id: str,
) -> TutoringCalendarEventMap | None:
    stmt = (
        select(TutoringCalendarEventMap)
        .where(TutoringCalendarEventMap.tutor_user_id == tutor_user_id)
        .where(TutoringCalendarEventMap.calendar_id == calendar_id)
        .where(TutoringCalendarEventMap.google_event_id == google_event_id)
    )
    return await session.scalar(stmt)


async def upsert_event_map(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    calendar_id: str,
    google_event_id: str,
    lesson_id: int,
    ical_uid: str | None = None,
    recurring_event_id: str | None = None,
    google_updated_at: datetime | None = None,
) -> TutoringCalendarEventMap:
    obj = await get_event_map(
        session,
        tutor_user_id=tutor_user_id,
        calendar_id=calendar_id,
        google_event_id=google_event_id,
    )

    if obj is None:
        obj = TutoringCalendarEventMap(
            tutor_user_id=tutor_user_id,
            calendar_id=calendar_id,
            google_event_id=google_event_id,
            lesson_id=lesson_id,
            ical_uid=ical_uid,
            recurring_event_id=recurring_event_id,
            google_updated_at=google_updated_at,
        )
        session.add(obj)
        await session.flush()
        return obj

    # update mapping if something changed (rare but possible)
    obj.lesson_id = lesson_id
    obj.ical_uid = ical_uid
    obj.recurring_event_id = recurring_event_id
    obj.google_updated_at = google_updated_at
    return obj