from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base
from core.shared.utils.time_helpers import utcnow
from pipubot.domains.tutoring.models.enums import LessonStatus
from pipubot.domains.tutoring.models.mixins import TutoringOwnedMixin


class TutoringLesson(TutoringOwnedMixin, Base):
    __tablename__ = "tutoring_lessons"

    id: Mapped[int] = mapped_column(primary_key=True)

    student_id: Mapped[int] = mapped_column(
        ForeignKey("tutoring_students.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )

    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    status: Mapped[LessonStatus] = mapped_column(default=LessonStatus.PLANNED, nullable=False)

    # Money snapshot for THIS lesson instance (important for history)
    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)
    rate_snapshot: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    charge_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

    notes: Mapped[str | None] = mapped_column(Text)

    # Google Calendar mapping
    google_calendar_id: Mapped[str | None] = mapped_column(String(256), index=True)
    google_event_id: Mapped[str | None] = mapped_column(String(256))
    google_recurring_event_id: Mapped[str | None] = mapped_column(String(256))
    google_ical_uid: Mapped[str | None] = mapped_column(String(256))
    google_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    meet_url: Mapped[str | None] = mapped_column(String(1024))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    student = relationship("TutoringStudent", back_populates="lessons")
    allocations = relationship("TutoringPaymentAllocation", back_populates="lesson")

    __table_args__ = (
        # Idempotency: one Google event -> one local lesson, scoped per tutor
        UniqueConstraint(
            "tutor_user_id",
            "google_calendar_id",
            "google_event_id",
            name="uq_tutoring_lessons_tutor_gcal_event",
        ),
        Index("ix_tutoring_lessons_tutor_start", "tutor_user_id", "start_at"),
        Index("ix_tutoring_lessons_tutor_student_start", "tutor_user_id", "student_id", "start_at"),
    )