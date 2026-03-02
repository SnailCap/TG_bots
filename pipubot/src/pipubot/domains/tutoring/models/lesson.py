# pipubot/domains/tutoring/models/lesson.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base
from core.shared.utils.time_helpers import utcnow
from pipubot.domains.tutoring.models.enums import (
    LessonConfirmationStatus,
    LessonExceptionCode,
    LessonStatus,
)
from pipubot.domains.tutoring.models.mixins import TutoringOwnedMixin


class TutoringLesson(TutoringOwnedMixin, Base):
    __tablename__ = "tutoring_lessons"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Can be NULL until you implement matching event -> student
    student_id: Mapped[int | None] = mapped_column(
        ForeignKey("tutoring_students.id", ondelete="RESTRICT"),
        index=True,
        nullable=True,
    )

    # --- planned (from calendar) ---
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    status: Mapped[LessonStatus] = mapped_column(
        Enum(LessonStatus, name="tutoring_lesson_status"),
        default=LessonStatus.PLANNED,
        nullable=False,
    )

    confirmation_status: Mapped[LessonConfirmationStatus] = mapped_column(
        Enum(LessonConfirmationStatus, name="tutoring_lesson_confirmation_status"),
        default=LessonConfirmationStatus.PENDING,
        nullable=False,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # UI/notes from calendar
    title: Mapped[str | None] = mapped_column(String(512))
    notes: Mapped[str | None] = mapped_column(Text)

    # --- money snapshot (planned) ---
    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)

    planned_rate_snapshot: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    planned_charge_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

    # --- actual (entered/confirmed by tutor) ---
    actual_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True)

    actual_rate_snapshot: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    actual_charge_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

    exception_code: Mapped[LessonExceptionCode] = mapped_column(
        Enum(LessonExceptionCode, name="tutoring_lesson_exception_code"),
        default=LessonExceptionCode.NONE,
        nullable=False,
    )
    exception_note: Mapped[str | None] = mapped_column(Text)

    # --- Google Calendar mapping (instance-level when singleEvents=true) ---
    google_calendar_id: Mapped[str | None] = mapped_column(String(256), index=True)
    google_event_id: Mapped[str | None] = mapped_column(String(256))
    google_recurring_event_id: Mapped[str | None] = mapped_column(String(256))
    google_ical_uid: Mapped[str | None] = mapped_column(String(256))
    google_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    meet_url: Mapped[str | None] = mapped_column(String(1024))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    student = relationship("TutoringStudent", back_populates="lessons")
    allocations = relationship("TutoringPaymentAllocation", back_populates="lesson")

    __table_args__ = (
        # Idempotency: one Google event instance -> one local lesson, scoped per tutor
        UniqueConstraint(
            "tutor_user_id",
            "google_calendar_id",
            "google_event_id",
            name="uq_tutoring_lessons_tutor_gcal_event",
        ),
        Index("ix_tutoring_lessons_tutor_start", "tutor_user_id", "start_at"),
        Index("ix_tutoring_lessons_tutor_student_start", "tutor_user_id", "student_id", "start_at"),

        # sanity checks
        CheckConstraint("end_at > start_at", name="ck_tut_lesson_planned_end_gt_start"),
        CheckConstraint(
            "(actual_start_at IS NULL AND actual_end_at IS NULL) OR (actual_end_at > actual_start_at)",
            name="ck_tut_lesson_actual_end_gt_start",
        ),
        CheckConstraint(
            "actual_duration_min IS NULL OR actual_duration_min >= 0",
            name="ck_tut_lesson_actual_duration_nonneg",
        ),
        CheckConstraint(
            "planned_charge_amount IS NULL OR planned_charge_amount >= 0",
            name="ck_tut_lesson_planned_charge_nonneg",
        ),
        CheckConstraint(
            "actual_charge_amount IS NULL OR actual_charge_amount >= 0",
            name="ck_tut_lesson_actual_charge_nonneg",
        ),
    )