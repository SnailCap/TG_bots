from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pipubot.domains.tutoring.enums.lesson import LessonStatus, LessonExceptionCode


@dataclass(frozen=True, slots=True)
class ConfirmLesson:
    tutor_user_id: int
    lesson_id: int

    # outcome
    status: LessonStatus

    # actual
    actual_duration_min: Optional[int] = None
    actual_start_at: Optional[datetime] = None
    actual_end_at: Optional[datetime] = None

    # optional money override (rate per hour or fixed if FIXED model)
    override_rate: Optional[Decimal] = None

    # exception markers
    exception_code: LessonExceptionCode = LessonExceptionCode.NONE
    exception_note: Optional[str] = None
