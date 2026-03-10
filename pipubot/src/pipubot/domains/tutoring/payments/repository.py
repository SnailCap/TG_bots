from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pipubot.domains.tutoring.enums.payment import PaymentMethod
from pipubot.domains.tutoring.models.payment import TutoringPayment


async def get_payment_by_id(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    payment_id: int,
) -> TutoringPayment | None:
    stmt = (
        select(TutoringPayment)
        .where(TutoringPayment.tutor_user_id == tutor_user_id)
        .where(TutoringPayment.id == payment_id)
    )
    return await session.scalar(stmt)


async def get_payment_by_external_ref(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    external_ref: str,
) -> TutoringPayment | None:
    stmt = (
        select(TutoringPayment)
        .where(TutoringPayment.tutor_user_id == tutor_user_id)
        .where(TutoringPayment.external_ref == external_ref)
    )
    return await session.scalar(stmt)


async def list_payments_for_student(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    student_id: int,
    limit: int = 200,
    offset: int = 0,
) -> list[TutoringPayment]:
    stmt = (
        select(TutoringPayment)
        .where(TutoringPayment.tutor_user_id == tutor_user_id)
        .where(TutoringPayment.student_id == student_id)
        .order_by(TutoringPayment.paid_at.desc(), TutoringPayment.id.desc())
        .limit(limit)
        .offset(offset)
    )
    res = await session.scalars(stmt)
    return list(res)


async def create_payment(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    student_id: int,
    paid_at: datetime,
    amount: Decimal,
    currency: str = "EUR",
    method: PaymentMethod = PaymentMethod.BANK_TRANSFER,
    external_ref: str | None = None,
    note: str | None = None,
) -> TutoringPayment:
    obj = TutoringPayment(
        tutor_user_id=tutor_user_id,
        student_id=student_id,
        paid_at=paid_at,
        amount=amount,
        currency=currency,
        method=method,
        external_ref=external_ref,
        note=note,
    )
    session.add(obj)
    return obj


async def sum_payments_for_student(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    student_id: int,
) -> Decimal:
    stmt = (
        select(func.coalesce(func.sum(TutoringPayment.amount), 0))
        .where(TutoringPayment.tutor_user_id == tutor_user_id)
        .where(TutoringPayment.student_id == student_id)
    )
    val = await session.scalar(stmt)
    return val  # type: ignore[return-value]