from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pipubot.domains.tutoring.models.allocation import TutoringPaymentAllocation


def create_allocation(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    payment_id: int,
    lesson_id: int,
    amount_applied: Decimal,
) -> TutoringPaymentAllocation:
    obj = TutoringPaymentAllocation(
        tutor_user_id=tutor_user_id,
        payment_id=payment_id,
        lesson_id=lesson_id,
        amount_applied=amount_applied,
    )
    session.add(obj)
    return obj


async def list_allocations_for_payment(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    payment_id: int,
) -> list[TutoringPaymentAllocation]:
    stmt = (
        select(TutoringPaymentAllocation)
        .where(TutoringPaymentAllocation.tutor_user_id == tutor_user_id)
        .where(TutoringPaymentAllocation.payment_id == payment_id)
        .order_by(TutoringPaymentAllocation.id.asc())
    )
    res = await session.scalars(stmt)
    return list(res)


async def list_allocations_for_lesson(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    lesson_id: int,
) -> list[TutoringPaymentAllocation]:
    stmt = (
        select(TutoringPaymentAllocation)
        .where(TutoringPaymentAllocation.tutor_user_id == tutor_user_id)
        .where(TutoringPaymentAllocation.lesson_id == lesson_id)
        .order_by(TutoringPaymentAllocation.id.asc())
    )
    res = await session.scalars(stmt)
    return list(res)


async def sum_payment_allocated(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    payment_id: int,
) -> Decimal:
    stmt = (
        select(func.coalesce(func.sum(TutoringPaymentAllocation.amount_applied), 0))
        .where(TutoringPaymentAllocation.tutor_user_id == tutor_user_id)
        .where(TutoringPaymentAllocation.payment_id == payment_id)
    )
    val = await session.scalar(stmt)
    return val  # type: ignore[return-value]


async def sum_lesson_allocated(
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