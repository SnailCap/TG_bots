# pipubot/domains/tutoring/models/student.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base
from core.shared.utils.time_helpers import utcnow
from pipubot.domains.tutoring.models.enums import BillingChargeModel, RoundingMode
from pipubot.domains.tutoring.models.mixins import TutoringOwnedMixin


class TutoringStudent(TutoringOwnedMixin, Base):
    __tablename__ = "tutoring_students"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Optional: if the student has the telegram, you can store it (NOT a FK to users by default)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    telegram_username: Mapped[str | None] = mapped_column(String, nullable=True)

    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Defaults
    default_currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)
    default_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

    # Common per-student defaults to avoid manual input every lesson
    default_duration_min: Mapped[int] = mapped_column(Integer, default=60, nullable=False)

    # Billing policy knobs (future-proof, but still simple)
    charge_model: Mapped[BillingChargeModel] = mapped_column(
        Enum(BillingChargeModel, name="tutoring_billing_charge_model"),
        default=BillingChargeModel.PER_HOUR,
        nullable=False,
    )

    rounding_minutes: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    rounding_mode: Mapped[RoundingMode] = mapped_column(
        Enum(RoundingMode, name="tutoring_rounding_mode"),
        default=RoundingMode.NEAREST,
        nullable=False,
    )

    # Minimum billable minutes (e.g., if the student is 5 min late, you still bill a full lesson)
    min_billable_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Cancellation/No-show fees (percentage of planned charge, 0..100)
    late_cancel_fee_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    no_show_fee_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Tallinn", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    lessons = relationship("TutoringLesson", back_populates="student")
    payments = relationship("TutoringPayment", back_populates="student")

    __table_args__ = (
        UniqueConstraint("tutor_user_id", "telegram_id", name="uq_tutoring_students_tutor_telegram"),
        Index(
            "uq_tutoring_students_active_name",
            "tutor_user_id",
            "full_name",
            unique=True,
            postgresql_where=text("is_active"),
        ),
        CheckConstraint("default_duration_min > 0", name="ck_tut_student_default_duration_positive"),
        CheckConstraint("rounding_minutes >= 0", name="ck_tut_student_rounding_nonneg"),
        CheckConstraint("min_billable_minutes >= 0", name="ck_tut_student_min_billable_nonneg"),
        CheckConstraint("late_cancel_fee_percent >= 0 AND late_cancel_fee_percent <= 100", name="ck_tut_student_late_cancel_fee_pct"),
        CheckConstraint("no_show_fee_percent >= 0 AND no_show_fee_percent <= 100", name="ck_tut_student_no_show_fee_pct"),
    )