from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.shared.utils.time import utc_now
from pipubot.domains.tutoring.enums.lesson import LessonStatus, LessonConfirmationStatus
from pipubot.domains.tutoring.models.lesson import TutoringLesson


# ============================================================
# Public queries
# ============================================================

async def get_lesson_by_id(
        session: AsyncSession,
        *,
        tutor_user_id: int,
        lesson_id: int,
        load_student: bool = False,
) -> TutoringLesson | None:
    stmt = (
        select(TutoringLesson)
        .where(TutoringLesson.tutor_user_id == tutor_user_id)
        .where(TutoringLesson.id == lesson_id)
    )
    if load_student:
        stmt = stmt.options(selectinload(TutoringLesson.student))
    return await session.scalar(stmt)


async def list_lessons(
        session: AsyncSession,
        *,
        tutor_user_id: int,
        limit: int = 200,
        offset: int = 0,
        load_student: bool = False,
        student_id: int | None = None,
        start_from: datetime | None = None,
        start_to: datetime | None = None,
        statuses: list[LessonStatus] | None = None,
        confirmation_status: LessonConfirmationStatus | None = None,
) -> list[TutoringLesson]:
    """
    Универсальный листинг уроков с поддержкой фильтров.
    """
    stmt: Select[tuple[TutoringLesson]] = select(TutoringLesson)
    stmt = _apply_lesson_filters(
        stmt,
        tutor_user_id=tutor_user_id,
        student_id=student_id,
        start_from=start_from,
        start_to=start_to,
        statuses=statuses,
        confirmation_status=confirmation_status,
    )

    stmt = stmt.order_by(TutoringLesson.start_at.asc(), TutoringLesson.id.asc()).limit(limit).offset(offset)

    if load_student:
        stmt = stmt.options(selectinload(TutoringLesson.student))

    res = await session.scalars(stmt)
    return list(res)


# ============================================================
# Google Calendar integration
# ============================================================

async def get_lesson_by_google_instance(
        session: AsyncSession,
        *,
        tutor_user_id: int,
        google_calendar_id: str,
        google_event_id: str,
) -> TutoringLesson | None:
    stmt = (
        select(TutoringLesson)
        .where(TutoringLesson.tutor_user_id == tutor_user_id)
        .where(TutoringLesson.google_calendar_id == google_calendar_id)
        .where(TutoringLesson.google_event_id == google_event_id)
    )
    return await session.scalar(stmt)


async def upsert_lesson_from_gcal_event(
        session: AsyncSession,
        *,
        tutor_user_id: int,
        google_calendar_id: str,
        google_event_id: str,
        start_at: datetime,
        end_at: datetime,
        status: LessonStatus,
        google_updated_at: datetime | None,
        google_ical_uid: str | None,
        google_recurring_event_id: str | None,
        title: str | None,
        description: str | None,
        meet_url: str | None,
        student_id: int | None,
        currency: str,
        planned_rate_snapshot: Decimal | None,
        planned_charge_amount: Decimal | None,
) -> TutoringLesson:
    stmt = (
        select(TutoringLesson)
        .where(TutoringLesson.tutor_user_id == tutor_user_id)
        .where(TutoringLesson.google_calendar_id == google_calendar_id)
        .where(TutoringLesson.google_event_id == google_event_id)
        .limit(1)
    )
    lesson = await session.scalar(stmt)

    if lesson is None:
        lesson = TutoringLesson(
            tutor_user_id=tutor_user_id,
            student_id=student_id,
            google_calendar_id=google_calendar_id,
            google_event_id=google_event_id,
            google_recurring_event_id=google_recurring_event_id,
            google_ical_uid=google_ical_uid,
            google_updated_at=google_updated_at,
            start_at=start_at,
            end_at=end_at,
            status=status,
            title=title,
            description=description,
            meet_url=meet_url,
            currency=currency,
            planned_rate_snapshot=planned_rate_snapshot,
            planned_charge_amount=planned_charge_amount,
        )
        session.add(lesson)
        await session.flush()
        return lesson

    lesson.student_id = student_id
    lesson.start_at = start_at
    lesson.end_at = end_at
    lesson.status = status
    lesson.google_updated_at = google_updated_at
    lesson.google_ical_uid = google_ical_uid
    lesson.google_recurring_event_id = google_recurring_event_id
    lesson.title = title
    lesson.description = description

    # ВАЖНО:
    # sync не должен затирать локально созданный meet_url значением None,
    # потому что Google conferenceData может появиться не мгновенно.
    if meet_url is not None:
        lesson.meet_url = meet_url

    lesson.currency = currency
    lesson.planned_rate_snapshot = planned_rate_snapshot
    lesson.planned_charge_amount = planned_charge_amount
    lesson.updated_at = utc_now()

    await session.flush()
    return lesson


async def update_lesson_meet_url(
        session: AsyncSession,
        *,
        tutor_user_id: int,
        lesson_id: int,
        meet_url: str,
) -> TutoringLesson | None:
    lesson = await get_lesson_by_id(
        session,
        tutor_user_id=tutor_user_id,
        lesson_id=lesson_id,
        load_student=False,
    )
    if lesson is None:
        return None

    lesson.meet_url = meet_url
    lesson.updated_at = utc_now()
    await session.flush()
    return lesson


async def list_upcoming_lessons(
        session: AsyncSession,
        *,
        tutor_user_id: int,
        start_from: datetime,
        start_to: datetime,
        limit: int = 200,
        load_student: bool = True,
) -> list[TutoringLesson]:
    """
    Upcoming lessons within [start_from, start_to).
    По умолчанию подгружаем student через selectinload,
    чтобы не словить MissingGreenlet в сервисах/хендлерах,
    которые читают lesson.student.
    """
    stmt = (
        select(TutoringLesson)
        .where(TutoringLesson.tutor_user_id == tutor_user_id)
        .where(TutoringLesson.start_at >= start_from)
        .where(TutoringLesson.start_at < start_to)
        .order_by(TutoringLesson.start_at.asc(), TutoringLesson.id.asc())
        .limit(limit)
    )

    if load_student:
        stmt = stmt.options(selectinload(TutoringLesson.student))

    res = await session.scalars(stmt)
    return list(res)


# ============================================================
# Internal helpers
# ============================================================

def _apply_lesson_filters(
        stmt: Select[tuple[TutoringLesson]],
        *,
        tutor_user_id: int,
        student_id: int | None,
        start_from: datetime | None,
        start_to: datetime | None,
        statuses: list[LessonStatus] | None,
        confirmation_status: LessonConfirmationStatus | None,
) -> Select[tuple[TutoringLesson]]:
    stmt = stmt.where(TutoringLesson.tutor_user_id == tutor_user_id)

    if student_id is not None:
        stmt = stmt.where(TutoringLesson.student_id == student_id)
    if start_from is not None:
        stmt = stmt.where(TutoringLesson.start_at >= start_from)
    if start_to is not None:
        stmt = stmt.where(TutoringLesson.start_at < start_to)
    if statuses:
        stmt = stmt.where(TutoringLesson.status.in_(statuses))
    if confirmation_status is not None:
        stmt = stmt.where(TutoringLesson.confirmation_status == confirmation_status)

    return stmt


async def update_lesson_miro_url(
        session: AsyncSession,
        *,
        tutor_user_id: int,
        lesson_id: int,
        miro_url: str,
) -> TutoringLesson | None:
    lesson = await get_lesson_by_id(
        session,
        tutor_user_id=tutor_user_id,
        lesson_id=lesson_id,
        load_student=False,
    )
    if lesson is None:
        return None

    lesson.miro_url = miro_url
    lesson.updated_at = utc_now()
    await session.flush()
    return lesson
