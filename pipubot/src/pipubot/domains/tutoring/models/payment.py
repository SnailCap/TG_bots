# pipubot/domains/tutoring/models/payment.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base
from core.shared.utils.time import utc_now
from pipubot.domains.tutoring.enums.enums import PaymentMethod
from pipubot.domains.tutoring.models.mixins import TutoringOwnedMixin


class TutoringPayment(TutoringOwnedMixin, Base):
    __tablename__ = "tutoring_payments"

    id: Mapped[int] = mapped_column(primary_key=True)

    student_id: Mapped[int] = mapped_column(
        ForeignKey("tutoring_students.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )

    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="tutoring_payment_method"),
        default=PaymentMethod.BANK_TRANSFER,
        nullable=False,
    )

    external_ref: Mapped[str | None] = mapped_column(String(256), index=True)
    note: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    student = relationship("TutoringStudent", back_populates="payments")
    allocations = relationship("TutoringPaymentAllocation", back_populates="payment")

    __table_args__ = (
        Index("ix_tutoring_payments_tutor_paid_at", "tutor_user_id", "paid_at"),
        Index("ix_tutoring_payments_tutor_student_paid_at", "tutor_user_id", "student_id", "paid_at"),
        CheckConstraint("amount > 0", name="ck_tut_payment_amount_positive"),
    )