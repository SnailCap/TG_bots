from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from core.db.transaction import transactional
from pipubot.domains.tutoring.models.enums import PaymentMethod
from pipubot.domains.tutoring.repositories.student_repository import get_student_by_id
from pipubot.domains.tutoring.repositories.lesson_repository import (
    list_unpaid_lessons,
    sum_student_paid_allocations,
)
from pipubot.domains.tutoring.repositories.payment_repository import (
    create_payment,
    get_payment_by_external_ref,
    sum_student_payments,
)
from pipubot.domains.tutoring.repositories.allocation_repository import (
    create_allocation,
    sum_payment_allocated,
)


class TutoringOwnershipError(RuntimeError):
    pass


@dataclass(frozen=True)
class PaymentAllocationResult:
    payment_id: int
    allocated_total: Decimal
    remaining_unallocated: Decimal
    allocations_created: int


@transactional
async def allocate_payment(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    student_id: int,
    amount: Decimal,
    paid_at: datetime,
    currency: str = "EUR",
    method: PaymentMethod = PaymentMethod.BANK_TRANSFER,
    external_ref: str | None = None,
    note: str | None = None,
    include_planned: bool = True,
    include_done: bool = True,
) -> PaymentAllocationResult:
    # ownership guard
    student = await get_student_by_id(session, tutor_user_id=tutor_user_id, student_id=student_id)
    if not student:
        raise TutoringOwnershipError("Student not found or not owned by tutor_user_id")

    # idempotent payment lookup by external_ref
    payment = None
    if external_ref:
        payment = await get_payment_by_external_ref(session, tutor_user_id=tutor_user_id, external_ref=external_ref)

    if payment is None:
        payment = await create_payment(
            session,
            tutor_user_id=tutor_user_id,
            student_id=student_id,
            paid_at=paid_at,
            amount=amount,
            currency=currency,
            method=method,
            external_ref=external_ref,
            note=note,
        )
        # Need id for allocations
        await session.flush()
    else:
        if payment.student_id != student_id:
            raise TutoringOwnershipError("Payment external_ref exists but linked to another student")
        await session.flush()

    already_allocated = await sum_payment_allocated(session, tutor_user_id=tutor_user_id, payment_id=payment.id)
    remaining = payment.amount - already_allocated

    if remaining <= 0:
        return PaymentAllocationResult(
            payment_id=payment.id,
            allocated_total=already_allocated,
            remaining_unallocated=Decimal("0.00"),
            allocations_created=0,
        )

    unpaid = await list_unpaid_lessons(
        session,
        tutor_user_id=tutor_user_id,
        student_id=student_id,
        include_planned=include_planned,
        include_done=include_done,
    )

    created = 0
    allocated_now = Decimal("0.00")

    for st in unpaid:
        if remaining <= 0:
            break

        due = st.charge_amount - st.paid_amount
        if due <= 0:
            continue

        apply_amount = due if due <= remaining else remaining

        await create_allocation(
            session,
            tutor_user_id=tutor_user_id,
            payment_id=payment.id,
            lesson_id=st.lesson_id,
            amount_applied=apply_amount,
        )

        created += 1
        allocated_now += apply_amount
        remaining -= apply_amount

    return PaymentAllocationResult(
        payment_id=payment.id,
        allocated_total=already_allocated + allocated_now,
        remaining_unallocated=remaining,
        allocations_created=created,
    )


async def get_student_balance(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    student_id: int,
) -> Decimal:
    """
    Positive = prepaid (credit), negative = debt.
    """
    student = await get_student_by_id(session, tutor_user_id=tutor_user_id, student_id=student_id)
    if not student:
        raise TutoringOwnershipError("Student not found or not owned by tutor_user_id")

    paid_total = await sum_student_payments(session, tutor_user_id=tutor_user_id, student_id=student_id)
    allocated_total = await sum_student_paid_allocations(session, tutor_user_id=tutor_user_id, student_id=student_id)
    return paid_total - allocated_total