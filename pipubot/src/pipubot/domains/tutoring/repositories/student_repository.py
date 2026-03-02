from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pipubot.domains.tutoring.models.student import TutoringStudent
from pipubot.domains.tutoring.utils.name_normalize import normalize_human_name
from pipubot.domains.tutoring.utils.sql_name_expr import normalized_name_expr


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


async def get_student_by_telegram_id(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    telegram_id: int,
) -> TutoringStudent | None:
    stmt = (
        select(TutoringStudent)
        .where(TutoringStudent.tutor_user_id == tutor_user_id)
        .where(TutoringStudent.telegram_id == telegram_id)
    )
    return await session.scalar(stmt)


async def list_active_students(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    limit: int = 100,
    offset: int = 0,
) -> list[TutoringStudent]:
    stmt = (
        select(TutoringStudent)
        .where(TutoringStudent.tutor_user_id == tutor_user_id)
        .where(TutoringStudent.is_active.is_(True))
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
            TutoringStudent.is_active.desc(),
            TutoringStudent.full_name.asc(),
            TutoringStudent.id.asc(),
        )
        .limit(limit)
    )

    res = await session.scalars(stmt)
    return list(res)

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
            TutoringStudent.is_active.desc(),
            TutoringStudent.full_name.asc(),
            TutoringStudent.id.asc(),
        )
        .limit(limit)
    )

    res = await session.scalars(stmt)
    return list(res)