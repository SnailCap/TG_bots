# pipubot/domains/tutoring/models/allocation.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base
from core.shared.utils.time import utc_now
from pipubot.domains.tutoring.models.mixins import TutoringOwnedMixin


class TutoringPaymentAllocation(TutoringOwnedMixin, Base):
    __tablename__ = "tutoring_payment_allocations"

    id: Mapped[int] = mapped_column(primary_key=True)

    payment_id: Mapped[int] = mapped_column(
        ForeignKey("tutoring_payments.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    lesson_id: Mapped[int] = mapped_column(
        ForeignKey("tutoring_lessons.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    amount_applied: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    payment = relationship("TutoringPayment", back_populates="allocations")
    lesson = relationship("TutoringLesson", back_populates="allocations")

    __table_args__ = (
        UniqueConstraint(
            "tutor_user_id",
            "payment_id",
            "lesson_id",
            name="uq_tutoring_alloc_tutor_payment_lesson",
        ),
        CheckConstraint("amount_applied > 0", name="ck_tutoring_alloc_amount_positive"),
        Index("ix_tutoring_alloc_tutor_lesson", "tutor_user_id", "lesson_id"),
        Index("ix_tutoring_alloc_tutor_payment", "tutor_user_id", "payment_id"),
    )