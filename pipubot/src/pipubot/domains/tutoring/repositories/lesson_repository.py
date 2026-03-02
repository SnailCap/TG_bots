from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pipubot.domains.tutoring.models.allocation import TutoringPaymentAllocation
from pipubot.domains.tutoring.models.enums import LessonConfirmationStatus, LessonStatus
from pipubot.domains.tutoring.models.lesson import TutoringLesson


@dataclass(frozen=True)
class LessonPaymentsSnapshotRow:
    """
    Raw snapshot row for services/UI:
    - planned/actual charges are returned as-is
    - paid_amount is sum(allocations.amount_applied)
    No business interpretation here.
    """
    lesson_id: int
    student_id: int | None
    status: LessonStatus
    confirmation_status: LessonConfirmationStatus
    start_at: datetime
    end_at: datetime
    currency: str

    planned_charge_amount: Decimal | None
    actual_charge_amount: Decimal | None
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


async def list_lessons_for_student(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    student_id: int,
    start_from: datetime | None = None,
    start_to: datetime | None = None,
    statuses: list[LessonStatus] | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[TutoringLesson]:
    stmt = (
        select(TutoringLesson)
        .where(TutoringLesson.tutor_user_id == tutor_user_id)
        .where(TutoringLesson.student_id == student_id)
    )

    if start_from is not None:
        stmt = stmt.where(TutoringLesson.start_at >= start_from)
    if start_to is not None:
        stmt = stmt.where(TutoringLesson.start_at < start_to)
    if statuses:
        stmt = stmt.where(TutoringLesson.status.in_(statuses))

    stmt = (
        stmt.order_by(TutoringLesson.start_at.asc(), TutoringLesson.id.asc())
        .limit(limit)
        .offset(offset)
    )

    res = await session.scalars(stmt)
    return list(res)


async def list_lessons_pending_confirmation(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    start_from: datetime | None = None,
    start_to: datetime | None = None,
    statuses: list[LessonStatus] | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[TutoringLesson]:
    """
    Pure data query: returns lessons where confirmation is pending.
    Which statuses mean "should be confirmed" is up to the service (pass statuses if needed).
    """
    stmt = (
        select(TutoringLesson)
        .where(TutoringLesson.tutor_user_id == tutor_user_id)
        .where(TutoringLesson.confirmation_status == LessonConfirmationStatus.PENDING)
    )

    if start_from is not None:
        stmt = stmt.where(TutoringLesson.start_at >= start_from)
    if start_to is not None:
        stmt = stmt.where(TutoringLesson.start_at < start_to)
    if statuses:
        stmt = stmt.where(TutoringLesson.status.in_(statuses))

    stmt = (
        stmt.order_by(TutoringLesson.start_at.asc(), TutoringLesson.id.asc())
        .limit(limit)
        .offset(offset)
    )

    res = await session.scalars(stmt)
    return list(res)


async def list_lessons_with_paid_amount_for_student(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    student_id: int,
    start_from: datetime | None = None,
    start_to: datetime | None = None,
    statuses: list[LessonStatus] | None = None,
    limit: int = 500,
) -> list[LessonPaymentsSnapshotRow]:
    """
    Raw financial snapshot rows for a student's lessons.
    - includes planned_charge_amount, actual_charge_amount, confirmation_status
    - includes paid_amount = sum(allocations)
    """
    alloc_sum = func.coalesce(func.sum(TutoringPaymentAllocation.amount_applied), 0)

    stmt = (
        select(
            TutoringLesson.id,
            TutoringLesson.student_id,
            TutoringLesson.status,
            TutoringLesson.confirmation_status,
            TutoringLesson.start_at,
            TutoringLesson.end_at,
            TutoringLesson.currency,
            TutoringLesson.planned_charge_amount,
            TutoringLesson.actual_charge_amount,
            alloc_sum.label("paid_amount"),
        )
        .outerjoin(
            TutoringPaymentAllocation,
            (TutoringPaymentAllocation.lesson_id == TutoringLesson.id)
            & (TutoringPaymentAllocation.tutor_user_id == tutor_user_id),
        )
        .where(TutoringLesson.tutor_user_id == tutor_user_id)
        .where(TutoringLesson.student_id == student_id)
        .group_by(
            TutoringLesson.id,
            TutoringLesson.student_id,
            TutoringLesson.status,
            TutoringLesson.confirmation_status,
            TutoringLesson.start_at,
            TutoringLesson.end_at,
            TutoringLesson.currency,
            TutoringLesson.planned_charge_amount,
            TutoringLesson.actual_charge_amount,
        )
        .order_by(TutoringLesson.start_at.asc(), TutoringLesson.id.asc())
        .limit(limit)
    )

    if start_from is not None:
        stmt = stmt.where(TutoringLesson.start_at >= start_from)
    if start_to is not None:
        stmt = stmt.where(TutoringLesson.start_at < start_to)
    if statuses:
        stmt = stmt.where(TutoringLesson.status.in_(statuses))

    rows = (await session.execute(stmt)).all()
    return [
        LessonPaymentsSnapshotRow(
            lesson_id=int(lesson_id),
            student_id=student_id,
            status=status,
            confirmation_status=confirmation_status,
            start_at=start_at,
            end_at=end_at,
            currency=currency,
            planned_charge_amount=planned_charge_amount,
            actual_charge_amount=actual_charge_amount,
            paid_amount=paid_amount,
        )
        for (
            lesson_id,
            student_id,
            status,
            confirmation_status,
            start_at,
            end_at,
            currency,
            planned_charge_amount,
            actual_charge_amount,
            paid_amount,
        ) in rows
    ]


async def get_lesson_paid_amount(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    lesson_id: int,
) -> Decimal:
    stmt = (
        select(func.coalesce(func.sum(TutoringPaymentAllocation.amount_applied), 0))
        .where(TutoringPaymentAllocation.tutor_user_id == tutor_user_id)
        .where(TutoringPaymentAllocation.lesson_id == lesson_id)
    )
    val = await session.scalar(stmt)
    return val  # type: ignore[return-value]


async def sum_student_planned_charges(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    student_id: int,
) -> Decimal:
    stmt = (
        select(func.coalesce(func.sum(TutoringLesson.planned_charge_amount), 0))
        .where(TutoringLesson.tutor_user_id == tutor_user_id)
        .where(TutoringLesson.student_id == student_id)
        .where(TutoringLesson.planned_charge_amount.is_not(None))
    )
    val = await session.scalar(stmt)
    return val  # type: ignore[return-value]


async def sum_student_actual_charges(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    student_id: int,
) -> Decimal:
    stmt = (
        select(func.coalesce(func.sum(TutoringLesson.actual_charge_amount), 0))
        .where(TutoringLesson.tutor_user_id == tutor_user_id)
        .where(TutoringLesson.student_id == student_id)
        .where(TutoringLesson.actual_charge_amount.is_not(None))
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
    meet_url: str | None = None,
    student_id: int | None = None,
) -> TutoringLesson:
    """
    Idempotent upsert for a Google Calendar *instance* (singleEvents=true).

    Repository rule:
    - updates ONLY calendar/planned fields
    - does NOT touch actual_* / confirmation_* / exception_* / money snapshots
    - if google_updated_at is present, prevents stale overwrites
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
            meet_url=meet_url,
        )
        session.add(lesson)
        await session.flush()
        return lesson

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
    if meet_url is not None:
        lesson.meet_url = meet_url

    # only set student if you resolved it (avoid wiping)
    if student_id is not None and lesson.student_id is None:
        lesson.student_id = student_id

    return lesson