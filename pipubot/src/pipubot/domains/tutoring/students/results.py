from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from pipubot.domains.tutoring.enums.student import StudentState, SchoolGrade, PaymentAccount, ExamTrack, StudyLanguage, \
    StudyFormat, Currency


@dataclass(slots=True)
class StudentDraft:
    """
    Mutable draft used while collecting student data from UI steps.
    """

    full_name: str | None = None

    user_telegram_id: int | None = None
    telegram_username: str | None = None
    telegram_link: str | None = None

    email: str | None = None
    google_drive_link: str | None = None

    school_grade: SchoolGrade | None = None
    exam_track: ExamTrack | None = None

    study_language: StudyLanguage | None = None
    study_format: StudyFormat | None = None

    started_on: date | None = None
    notes: str | None = None

    default_currency: Currency | None = Currency.EUR
    default_rate: Decimal | None = None
    default_duration_min: int | None = 60

    planned_hours_per_week: Decimal | None = None
    payment_account: PaymentAccount | None = None

    student_state: StudentState | None = StudentState.ACTIVE


