from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, Numeric, String, UniqueConstraint, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base
from core.shared.utils.time_helpers import utcnow
from pipubot.domains.tutoring.models.mixins import TutoringOwnedMixin


class TutoringStudent(TutoringOwnedMixin, Base):
    __tablename__ = "tutoring_students"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Optional: if the student has telegram, you can store it (NOT a FK to users by default)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    telegram_username: Mapped[str | None] = mapped_column(String, nullable=True)

    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    default_currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)
    default_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
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
    )