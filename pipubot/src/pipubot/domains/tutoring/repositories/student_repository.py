from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pipubot.domains.tutoring.models.student import TutoringStudent


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