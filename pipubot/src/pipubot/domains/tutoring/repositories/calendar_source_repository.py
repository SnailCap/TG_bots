from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pipubot.domains.tutoring.enums.enums import CalendarSourceStatus
from pipubot.domains.tutoring.models.calendar_source import TutoringCalendarSource


async def get_calendar_source(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    calendar_id: str,
) -> TutoringCalendarSource | None:
    stmt = (
        select(TutoringCalendarSource)
        .where(TutoringCalendarSource.tutor_user_id == tutor_user_id)
        .where(TutoringCalendarSource.calendar_id == calendar_id)
    )
    return await session.scalar(stmt)


async def upsert_calendar_source(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    calendar_id: str,
) -> TutoringCalendarSource:
    obj = await get_calendar_source(session, tutor_user_id=tutor_user_id, calendar_id=calendar_id)
    if obj:
        return obj

    obj = TutoringCalendarSource(
        tutor_user_id=tutor_user_id,
        calendar_id=calendar_id,
        status=CalendarSourceStatus.ACTIVE,
    )
    session.add(obj)
    await session.flush()
    return obj


async def set_sync_token(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    calendar_id: str,
    sync_token: str | None,
) -> None:
    obj = await upsert_calendar_source(session, tutor_user_id=tutor_user_id, calendar_id=calendar_id)
    obj.sync_token = sync_token


async def set_last_synced_at(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    calendar_id: str,
    last_synced_at: datetime | None,
) -> None:
    obj = await upsert_calendar_source(session, tutor_user_id=tutor_user_id, calendar_id=calendar_id)
    obj.last_synced_at = last_synced_at


async def set_window_days(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    calendar_id: str,
    window_days: int,
) -> None:
    obj = await upsert_calendar_source(session, tutor_user_id=tutor_user_id, calendar_id=calendar_id)
    obj.window_days = window_days


async def set_calendar_source_status(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    calendar_id: str,
    status: CalendarSourceStatus,
) -> None:
    obj = await upsert_calendar_source(session, tutor_user_id=tutor_user_id, calendar_id=calendar_id)
    obj.status = status


async def mark_reauth_required(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    calendar_id: str,
) -> None:
    obj = await upsert_calendar_source(session, tutor_user_id=tutor_user_id, calendar_id=calendar_id)
    obj.status = CalendarSourceStatus.REAUTH_REQUIRED
    obj.sync_token = None


async def activate_calendar_source(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    calendar_id: str,
) -> None:
    obj = await upsert_calendar_source(session, tutor_user_id=tutor_user_id, calendar_id=calendar_id)
    obj.status = CalendarSourceStatus.ACTIVE