from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from pipubot.domains.tutoring.enums.student import SchoolGrade, ExamTrack, StudyLanguage, StudyFormat, PaymentAccount, \
    StudentState


@dataclass(frozen=True, slots=True)
class CreateStudent:
    """
    Service-layer DTO for creating a student.
    """

    tutor_user_id: int
    full_name: str

    user_telegram_id: int | None
    telegram_username: str | None
    telegram_link: str | None

    email: str | None
    google_drive_link: str | None

    school_grade: SchoolGrade | None
    exam_track: ExamTrack | None

    study_language: StudyLanguage | None
    study_format: StudyFormat | None

    started_on: date | None
    notes: str | None

    default_currency: str
    default_rate: Decimal | None
    default_duration_min: int

    planned_hours_per_week: Decimal | None
    payment_account: PaymentAccount | None

    student_state: StudentState


@dataclass(frozen=True, slots=True)
class CreateStudentPersistPayload:
    """
    Repository-layer payload for inserting a student row.
    Must contain only normalized values ready for persistence.
    """

    tutor_user_id: int
    full_name: str

    user_telegram_id: int | None
    telegram_username: str | None
    telegram_link: str | None

    email: str | None
    google_drive_link: str | None

    school_grade: SchoolGrade | None
    exam_track: ExamTrack | None

    study_language: StudyLanguage | None
    study_format: StudyFormat | None

    started_on: date | None
    notes: str | None

    default_currency: str
    default_rate: Decimal | None
    default_duration_min: int

    planned_hours_per_week: Decimal | None
    payment_account: PaymentAccount | None

    student_state: StudentState
