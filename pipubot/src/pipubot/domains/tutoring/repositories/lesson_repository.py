from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pipubot.domains.tutoring.models.allocation import TutoringPaymentAllocation
from pipubot.domains.tutoring.models.enums import LessonStatus
from pipubot.domains.tutoring.models.lesson import TutoringLesson


@dataclass(frozen=True)
class LessonPaymentState:
    lesson_id: int
    charge_amount: Decimal
    paid_amount: Decimal


async def get_lesson_by_id(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    lesson_id: int,
) -> TutoringLesson | None:
    stmt = (
        select(TutoringLesson)
        .where(TutoringLesson.tutor_user_id == tutor_user_id)
        .where(TutoringLesson.id == lesson_id)
    )
    return await session.scalar(stmt)


async def list_unpaid_lessons(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    student_id: int,
    include_planned: bool = True,
    include_done: bool = True,
    limit: int = 200,
) -> list[LessonPaymentState]:
    allowed_statuses: list[LessonStatus] = []
    if include_planned:
        allowed_statuses.append(LessonStatus.PLANNED)
    if include_done:
        allowed_statuses.append(LessonStatus.DONE)

    if not allowed_statuses:
        return []

    alloc_sum = func.coalesce(func.sum(TutoringPaymentAllocation.amount_applied), 0)

    stmt = (
        select(
            TutoringLesson.id,
            TutoringLesson.charge_amount,
            alloc_sum.label("paid_amount"),
        )
        .outerjoin(
            TutoringPaymentAllocation,
            (TutoringPaymentAllocation.lesson_id == TutoringLesson.id)
            & (TutoringPaymentAllocation.tutor_user_id == tutor_user_id),
        )
        .where(TutoringLesson.tutor_user_id == tutor_user_id)
        .where(TutoringLesson.student_id == student_id)
        .where(TutoringLesson.charge_amount.is_not(None))
        .where(TutoringLesson.status.in_(allowed_statuses))
        .group_by(TutoringLesson.id, TutoringLesson.charge_amount)
        .having(alloc_sum < TutoringLesson.charge_amount)
        .order_by(TutoringLesson.start_at.asc())
        .limit(limit)
    )

    rows = (await session.execute(stmt)).all()
    return [
        LessonPaymentState(
            lesson_id=int(lesson_id),
            charge_amount=charge_amount,
            paid_amount=paid_amount,
        )
        for lesson_id, charge_amount, paid_amount in rows
    ]


async def get_lesson_payment_state(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    lesson_id: int,
) -> LessonPaymentState | None:
    alloc_sum = func.coalesce(func.sum(TutoringPaymentAllocation.amount_applied), 0)

    stmt = (
        select(
            TutoringLesson.id,
            TutoringLesson.charge_amount,
            alloc_sum.label("paid_amount"),
        )
        .outerjoin(
            TutoringPaymentAllocation,
            (TutoringPaymentAllocation.lesson_id == TutoringLesson.id)
            & (TutoringPaymentAllocation.tutor_user_id == tutor_user_id),
        )
        .where(TutoringLesson.tutor_user_id == tutor_user_id)
        .where(TutoringLesson.id == lesson_id)
        .where(TutoringLesson.charge_amount.is_not(None))
        .group_by(TutoringLesson.id, TutoringLesson.charge_amount)
    )

    row = (await session.execute(stmt)).one_or_none()
    if not row:
        return None

    l_id, charge_amount, paid_amount = row
    return LessonPaymentState(
        lesson_id=int(l_id),
        charge_amount=charge_amount,
        paid_amount=paid_amount,
    )


async def sum_student_charges(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    student_id: int,
) -> Decimal:
    stmt = (
        select(func.coalesce(func.sum(TutoringLesson.charge_amount), 0))
        .where(TutoringLesson.tutor_user_id == tutor_user_id)
        .where(TutoringLesson.student_id == student_id)
        .where(TutoringLesson.charge_amount.is_not(None))
    )
    val = await session.scalar(stmt)
    return val  # type: ignore[return-value]


async def sum_student_paid_allocations(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    student_id: int,
) -> Decimal:
    stmt = (
        select(func.coalesce(func.sum(TutoringPaymentAllocation.amount_applied), 0))
        .join(TutoringLesson, TutoringLesson.id == TutoringPaymentAllocation.lesson_id)
        .where(TutoringPaymentAllocation.tutor_user_id == tutor_user_id)
        .where(TutoringLesson.tutor_user_id == tutor_user_id)
        .where(TutoringLesson.student_id == student_id)
    )
    val = await session.scalar(stmt)
    return val  # type: ignore[return-value]


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
    google_updated_at: datetime | None = None,
    google_ical_uid: str | None = None,
    google_recurring_event_id: str | None = None,
    title: str | None = None,
    description: str | None = None,
    student_id: int | None = None,
) -> TutoringLesson:
    """
    Idempotent upsert for a Google Calendar *instance* (singleEvents=true).

    Money fields are NOT modified here.
    We also avoid "older update overwrote newer" if google_updated_at is provided.
    """
    lesson = await get_lesson_by_google_instance(
        session,
        tutor_user_id=tutor_user_id,
        google_calendar_id=google_calendar_id,
        google_event_id=google_event_id,
    )

    if lesson is None:
        lesson = TutoringLesson(
            tutor_user_id=tutor_user_id,
            student_id=student_id,
            status=status,
            start_at=start_at,
            end_at=end_at,
            google_calendar_id=google_calendar_id,
            google_event_id=google_event_id,
            google_updated_at=google_updated_at,
            google_ical_uid=google_ical_uid,
            google_recurring_event_id=google_recurring_event_id,
            title=title,
            notes=description,
        )
        session.add(lesson)
        await session.flush()
        return lesson

    # If we have timestamps, prevent stale overwrites
    if google_updated_at and lesson.google_updated_at and google_updated_at <= lesson.google_updated_at:
        return lesson

    lesson.start_at = start_at
    lesson.end_at = end_at
    lesson.status = status

    lesson.google_updated_at = google_updated_at
    lesson.google_ical_uid = google_ical_uid
    lesson.google_recurring_event_id = google_recurring_event_id

    if title is not None:
        lesson.title = title
    if description is not None:
        lesson.notes = description

    # only set student if you actually resolved it (so you don't wipe it accidentally)
    if student_id is not None and lesson.student_id is None:
        lesson.student_id = student_id

    return lesson