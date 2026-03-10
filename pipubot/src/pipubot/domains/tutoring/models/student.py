from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base
from core.shared.utils.time import utc_now
from pipubot.domains.tutoring.enums.payment import BillingChargeModel, RoundingMode
from pipubot.domains.tutoring.enums.student import StudentState, SchoolGrade, PaymentAccount, ExamTrack, StudyLanguage, \
    StudyFormat
from pipubot.domains.tutoring.models.mixins import TutoringOwnedMixin


class TutoringStudent(TutoringOwnedMixin, Base):
    __tablename__ = "tutoring_students"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Optional link to a real bot user from the shared users table.
    user_telegram_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    user = relationship(
        "User",
        foreign_keys=[user_telegram_id],
        lazy="joined",
    )

    # -------------------------
    # Core profile
    # -------------------------
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)

    student_state: Mapped[StudentState] = mapped_column(
        Enum(StudentState, name="tutoring_student_state"),
        default=StudentState.ACTIVE,
        nullable=False,
        index=True,
    )

    school_grade: Mapped[SchoolGrade | None] = mapped_column(
        Enum(SchoolGrade, name="tutoring_school_grade"),
        nullable=True,
        index=True,
    )

    exam_track: Mapped[ExamTrack | None] = mapped_column(
        Enum(ExamTrack, name="tutoring_exam_track"),
        nullable=True,
        index=True,
    )

    study_language: Mapped[StudyLanguage | None] = mapped_column(
        Enum(StudyLanguage, name="tutoring_study_language"),
        nullable=True,
        index=True,
    )

    study_format: Mapped[StudyFormat | None] = mapped_column(
        Enum(StudyFormat, name="tutoring_study_format"),
        nullable=True,
        index=True,
    )

    started_on: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # -------------------------
    # Contacts / links
    # -------------------------
    telegram_username: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    telegram_link: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )

    email: Mapped[str | None] = mapped_column(
        String(320),
        nullable=True,
    )

    google_drive_link: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
    )

    # -------------------------
    # Financial / planning defaults
    # -------------------------
    default_currency: Mapped[str] = mapped_column(
        String(3),
        default="EUR",
        nullable=False,
    )

    default_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    default_duration_min: Mapped[int] = mapped_column(
        Integer,
        default=60,
        nullable=False,
    )

    planned_hours_per_week: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )

    payment_account: Mapped[PaymentAccount | None] = mapped_column(
        Enum(PaymentAccount, name="tutoring_payment_account"),
        nullable=True,
        index=True,
    )

    # -------------------------
    # Existing billing knobs
    # -------------------------
    charge_model: Mapped[BillingChargeModel] = mapped_column(
        Enum(BillingChargeModel, name="tutoring_billing_charge_model"),
        default=BillingChargeModel.PER_HOUR,
        nullable=False,
    )

    rounding_minutes: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=False,
    )

    rounding_mode: Mapped[RoundingMode] = mapped_column(
        Enum(RoundingMode, name="tutoring_rounding_mode"),
        default=RoundingMode.NEAREST,
        nullable=False,
    )

    min_billable_minutes: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    late_cancel_fee_percent: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    no_show_fee_percent: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # -------------------------
    # Technical
    # -------------------------
    timezone: Mapped[str] = mapped_column(
        String(64),
        default="Europe/Tallinn",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    lessons = relationship("TutoringLesson", back_populates="student")
    payments = relationship("TutoringPayment", back_populates="student")

    __table_args__ = (
        UniqueConstraint(
            "tutor_user_id",
            "user_telegram_id",
            name="uq_tutoring_students_tutor_user_user_telegram",
        ),
        Index(
            "uq_tutoring_students_live_name",
            "tutor_user_id",
            "full_name",
            unique=True,
            postgresql_where=text(
                "student_state IN ('ACTIVE', 'PAUSED')"
            ),
        ),
        CheckConstraint(
            "default_duration_min > 0",
            name="ck_tut_student_default_duration_positive",
        ),
        CheckConstraint(
            "planned_hours_per_week IS NULL OR planned_hours_per_week > 0",
            name="ck_tut_student_planned_hours_per_week_positive",
        ),
        CheckConstraint(
            "rounding_minutes >= 0",
            name="ck_tut_student_rounding_nonneg",
        ),
        CheckConstraint(
            "min_billable_minutes >= 0",
            name="ck_tut_student_min_billable_nonneg",
        ),
        CheckConstraint(
            "late_cancel_fee_percent >= 0 AND late_cancel_fee_percent <= 100",
            name="ck_tut_student_late_cancel_fee_pct",
        ),
        CheckConstraint(
            "no_show_fee_percent >= 0 AND no_show_fee_percent <= 100",
            name="ck_tut_student_no_show_fee_pct",
        ),
    )