from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from pipubot.domains.tutoring.enums.lesson import LessonStatus, LessonConfirmationStatus


@dataclass(frozen=True)
class LessonPaymentsSnapshotRow:
    """
    Данные о платежах по уроку для UI/сервисов.
    """
    lesson_id: int
    student_id: int | None
    status: LessonStatus
    confirmation_status: LessonConfirmationStatus
    start_at: datetime
    end_at: datetime
    currency: str
    planned_charge_amount: Decimal | None
    actual_charge_amount: Decimal | None
    paid_amount: Decimal


@dataclass(frozen=True, slots=True)
class LessonReminderCandidate:
    # routing / idempotency
    chat_id: int
    dedupe_key: str

    # identity
    tutor_user_id: int
    before_minutes: int
    lesson_id: int

    # student
    student_id: int | None
    student_name: str | None

    # time
    start_at: datetime
    end_at: datetime
    start_hm: str
    end_hm: str
    duration_min: int

    # UI / notes
    title: str
    meet_url: str | None

    # money snapshot
    currency: str
    planned_rate_snapshot: Decimal | None
    planned_charge_amount: Decimal | None
    actual_rate_snapshot: Decimal | None
    actual_charge_amount: Decimal | None

    # statuses
    lesson_status: LessonStatus
    confirmation_status: LessonConfirmationStatus
