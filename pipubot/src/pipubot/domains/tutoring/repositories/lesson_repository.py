from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pipubot.domains.tutoring.enums.enums import LessonConfirmationStatus, LessonStatus
from pipubot.domains.tutoring.models.lesson import TutoringLesson


# ============================================================
# DTOs (optional, but keeps UI/service queries tidy)
# ============================================================

@dataclass(frozen=True)
class LessonPaymentsSnapshotRow:
    """
    Данные о платежах по уроку для UI/сервисов.
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
    # filters:
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
    **fields: Any,
) -> TutoringLesson:
    """
    Идемпотентный апсерт lesson из gcal instance (singleEvents=true).
    Guard-clause: если google_updated_at не новее — не трогаем запись.
    """
    lesson = await get_lesson_by_google_instance(
        session,
        tutor_user_id=tutor_user_id,
        google_calendar_id=google_calendar_id,
        google_event_id=google_event_id,
    )

    if lesson is None:
        return await _create_new_lesson(
            session,
            tutor_user_id=tutor_user_id,
            google_calendar_id=google_calendar_id,
            google_event_id=google_event_id,
            fields=fields,
        )

    new_updated = fields.get("google_updated_at")
    if new_updated and lesson.google_updated_at and new_updated <= lesson.google_updated_at:
        return lesson

    _update_lesson_attributes(lesson, fields)
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
    По умолчанию подгружаем student через deselection, чтобы не словить MissingGreenlet
    в сервисах/хендлерах, которые читают lesson.student.
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


async def _create_new_lesson(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    google_calendar_id: str,
    google_event_id: str,
    fields: dict[str, Any],
) -> TutoringLesson:
    lesson = TutoringLesson(
        tutor_user_id=tutor_user_id,
        google_calendar_id=google_calendar_id,
        google_event_id=google_event_id,
        **fields,
    )
    session.add(lesson)
    await session.flush()
    return lesson


def _update_lesson_attributes(lesson: TutoringLesson, fields: dict[str, Any]) -> None:
    """
    Обновление полей с простыми правилами:
    - не затираем student_id, если уже привязан
    - None не пишем, кроме "всегда обновляемых"
    - description -> notes (если вы именно так мапите)
    """
    always_updated: set[str] = {"start_at", "end_at", "status"}

    for key, value in fields.items():
        if value is None and key not in always_updated:
            continue

        if key == "student_id" and lesson.student_id is not None:
            continue

        attr_name = "notes" if key == "description" else key
        if hasattr(lesson, attr_name):
            setattr(lesson, attr_name, value)