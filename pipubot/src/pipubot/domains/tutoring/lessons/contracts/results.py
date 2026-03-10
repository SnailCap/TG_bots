from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pipubot.domains.tutoring.enums.lesson import LessonStatus


@dataclass(frozen=True, slots=True)
class ConfirmLessonResult:
    lesson_id: int
    student_id: int | None
    student_name: str | None
    status: LessonStatus
    actual_charge_amount: Decimal | None


@dataclass(frozen=True, slots=True)
class LessonPreparationStats:
    scanned_lessons: int = 0

    prepared_meet_links: int = 0
    prepared_miro_boards: int = 0

    skipped_existing_meet_links: int = 0
    skipped_existing_miro_boards: int = 0

    skipped_non_planned: int = 0
    skipped_past_or_started: int = 0
    skipped_unbound: int = 0

    failed_meet: int = 0
    failed_miro: int = 0
