from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from pipubot.domains.tutoring.enums.enums import (
    ExamTrack,
    PaymentAccount,
    SchoolGrade,
    StudentState,
    StudyFormat,
    StudyLanguage,
)


@dataclass(slots=True)
class StudentDraftDTO:
    """
    Mutable draft used while collecting student data from UI steps.
    """

    full_name: str | None = None

    telegram_link: str | None = None

    email: str | None = None
    google_drive_link: str | None = None

    school_grade: SchoolGrade | None = None
    exam_track: ExamTrack | None = None

    study_language: StudyLanguage | None = None
    study_format: StudyFormat | None = None

    started_on: date | None = None
    notes: str | None = None

    default_currency: str | None = "EUR"
    default_rate: Decimal | None = None
    default_duration_min: int | None = 60

    planned_hours_per_week: Decimal | None = None

    student_state: StudentState | None = StudentState.ACTIVE


@dataclass(frozen=True, slots=True)
class CreateStudentDTO:
    """
    Service-layer DTO for creating a student.
    """

    tutor_user_id: int
    full_name: str

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
class CreateStudentRepoPayload:
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