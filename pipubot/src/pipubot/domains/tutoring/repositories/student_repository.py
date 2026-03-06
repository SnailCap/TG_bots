from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pipubot.domains.tutoring.dto.student_dto import CreateStudentRepoPayload
from pipubot.domains.tutoring.enums.enums import StudentState
from pipubot.domains.tutoring.models.student import TutoringStudent
from pipubot.domains.tutoring.utils.name_normalize import normalize_human_name
from pipubot.domains.tutoring.utils.sql_name_expr import normalized_name_expr


_LIVE_STUDENT_STATES = (
    StudentState.ACTIVE,
    StudentState.PAUSED,
)


async def get_student_by_id(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    student_id: int,
) -> TutoringStudent | None:
    stmt = (
        select(TutoringStudent)
        .where(TutoringStudent.tutor_user_id == tutor_user_id)
        .where(TutoringStudent.id == student_id)
    )
    return await session.scalar(stmt)


async def get_student_by_user_telegram_id(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    user_telegram_id: int,
) -> TutoringStudent | None:
    stmt = (
        select(TutoringStudent)
        .where(TutoringStudent.tutor_user_id == tutor_user_id)
        .where(TutoringStudent.user_telegram_id == user_telegram_id)
    )
    return await session.scalar(stmt)


async def list_live_students(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    limit: int = 100,
    offset: int = 0,
) -> list[TutoringStudent]:
    stmt = (
        select(TutoringStudent)
        .where(TutoringStudent.tutor_user_id == tutor_user_id)
        .where(TutoringStudent.student_state.in_(_LIVE_STUDENT_STATES))
        .order_by(TutoringStudent.full_name.asc(), TutoringStudent.id.asc())
        .limit(limit)
        .offset(offset)
    )
    res = await session.scalars(stmt)
    return list(res)


async def list_students_by_full_name_ci(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    full_name: str,
    limit: int = 50,
) -> list[TutoringStudent]:
    key = normalize_human_name(full_name)
    if not key:
        return []

    norm_full_name = normalized_name_expr(TutoringStudent.full_name)

    stmt = (
        select(TutoringStudent)
        .where(TutoringStudent.tutor_user_id == tutor_user_id)
        .where(norm_full_name == key)
        .order_by(
            TutoringStudent.student_state.asc(),
            TutoringStudent.full_name.asc(),
            TutoringStudent.id.asc(),
        )
        .limit(limit)
    )

    res = await session.scalars(stmt)
    return list(res)


async def get_live_student_by_full_name_ci(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    full_name: str,
) -> TutoringStudent | None:
    key = normalize_human_name(full_name)
    if not key:
        return None

    norm_full_name = normalized_name_expr(TutoringStudent.full_name)

    stmt = (
        select(TutoringStudent)
        .where(TutoringStudent.tutor_user_id == tutor_user_id)
        .where(TutoringStudent.student_state.in_(_LIVE_STUDENT_STATES))
        .where(norm_full_name == key)
        .order_by(TutoringStudent.id.asc())
        .limit(1)
    )
    return await session.scalar(stmt)


async def list_students_by_first_name_ci(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    first_name: str,
    limit: int = 50,
) -> list[TutoringStudent]:
    key = normalize_human_name(first_name)
    if not key:
        return []

    norm_full_name = normalized_name_expr(TutoringStudent.full_name)

    stmt = (
        select(TutoringStudent)
        .where(TutoringStudent.tutor_user_id == tutor_user_id)
        .where(
            (norm_full_name == key)
            | (norm_full_name.like(f"{key} %"))
        )
        .order_by(
            TutoringStudent.student_state.asc(),
            TutoringStudent.full_name.asc(),
            TutoringStudent.id.asc(),
        )
        .limit(limit)
    )

    res = await session.scalars(stmt)
    return list(res)


async def create_student(
    session: AsyncSession,
    *,
    payload: CreateStudentRepoPayload,
) -> TutoringStudent:
    student = TutoringStudent(
        tutor_user_id=payload.tutor_user_id,
        full_name=payload.full_name,
        user_telegram_id=payload.user_telegram_id,
        telegram_username=payload.telegram_username,
        telegram_link=payload.telegram_link,
        email=payload.email,
        google_drive_link=payload.google_drive_link,
        school_grade=payload.school_grade,
        exam_track=payload.exam_track,
        study_language=payload.study_language,
        study_format=payload.study_format,
        started_on=payload.started_on,
        notes=payload.notes,
        default_currency=payload.default_currency,
        default_rate=payload.default_rate,
        default_duration_min=payload.default_duration_min,
        planned_hours_per_week=payload.planned_hours_per_week,
        payment_account=payload.payment_account,
        student_state=payload.student_state,
    )
    session.add(student)
    await session.flush()
    return student