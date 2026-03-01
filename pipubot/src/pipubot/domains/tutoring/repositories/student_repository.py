from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from pipubot.domains.tutoring.models.student import TutoringStudent


def _norm_spaces(s: str) -> str:
    return " ".join(s.split())


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
        .order_by(TutoringStudent.full_name.asc())
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
    """
    Case-insensitive exact match by full_name.
    """
    full_name = _norm_spaces(full_name).casefold()

    stmt = (
        select(TutoringStudent)
        .where(TutoringStudent.tutor_user_id == tutor_user_id)
        .where(func.lower(TutoringStudent.full_name) == full_name)
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
    """
    Case-insensitive match for:
    - full_name == first_name
    - full_name starts with 'first_name ' (so "Анна Петрова" matches "Анна")
    """
    first_name = _norm_spaces(first_name).casefold()

    stmt = (
        select(TutoringStudent)
        .where(TutoringStudent.tutor_user_id == tutor_user_id)
        .where(
            (func.lower(TutoringStudent.full_name) == first_name)
            | (func.lower(TutoringStudent.full_name).like(f"{first_name} %"))
        )
        .order_by(TutoringStudent.is_active.desc(), TutoringStudent.full_name.asc())
        .limit(limit)
    )
    res = await session.scalars(stmt)
    return list(res)
