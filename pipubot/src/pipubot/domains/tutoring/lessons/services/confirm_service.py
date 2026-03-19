from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

import pendulum
from sqlalchemy.ext.asyncio import AsyncSession

from core.shared.utils.time import utc_now
from core.shared.utils.time import round_minutes_to_step
from pipubot.domains.tutoring.enums.payment import BillingChargeModel
from pipubot.domains.tutoring.enums.lesson import LessonStatus, LessonConfirmationStatus
from pipubot.domains.tutoring.lessons.contracts.commands import ConfirmLesson
from pipubot.domains.tutoring.lessons.contracts.results import ConfirmLessonResult
from pipubot.domains.tutoring.shared.errors import (
    InvalidConfirmPayloadError,
    LessonAlreadyConfirmedError,
    LessonNotFoundError,
    StudentNotFoundError,
)
from pipubot.domains.tutoring.models.lesson import TutoringLesson
from pipubot.domains.tutoring.models.student import TutoringStudent
from pipubot.domains.tutoring.lessons.repository import get_lesson_by_id
from pipubot.domains.tutoring.students.repository import get_student_by_id


# ============================================================
# Time helpers (local, minimal)
# ============================================================

def _duration_minutes_floor(start: datetime, end: datetime) -> int:
    """
    Floor minutes between two datetime.
    Raises ValueError if the end <= starts.
    """
    start_p = pendulum.instance(start)
    end_p = pendulum.instance(end)

    if end_p <= start_p:
        raise ValueError("end must be > start")

    seconds = (end_p - start_p).total_seconds()
    return int(seconds // 60)


# ============================================================
# Money helpers
# ============================================================

def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _calc_charge_amount(
        *,
        student: TutoringStudent,
        duration_min: int,
        rate: Decimal,
) -> Decimal:
    """
    Compute lesson charge using student's billing policy.
    - min_billable_minutes
    - rounding_minutes + rounding_mode
    - Charge_model
    """
    bill_min = max(duration_min, student.min_billable_minutes)
    bill_min = round_minutes_to_step(bill_min, student.rounding_minutes, student.rounding_mode)

    if student.charge_model == BillingChargeModel.FIXED:
        return _money(rate)

    if student.charge_model == BillingChargeModel.PER_MINUTE:
        per_min = rate / Decimal(60)
        return _money(per_min * Decimal(bill_min))

    # PER_HOUR (default)
    hours = Decimal(bill_min) / Decimal(60)
    return _money(rate * hours)


# ============================================================
# Resolve helpers
# ============================================================

def _ensure_can_confirm(lesson: TutoringLesson, *, allow_update_confirmed: bool) -> None:
    if lesson.confirmation_status == LessonConfirmationStatus.CONFIRMED and not allow_update_confirmed:
        raise LessonAlreadyConfirmedError(f"Lesson {lesson.id} already confirmed")


async def _load_student_or_raise(
        session: AsyncSession,
        *,
        tutor_user_id: int,
        lesson: TutoringLesson,
) -> Optional[TutoringStudent]:
    if lesson.student_id is None:
        return None

    student = await get_student_by_id(
        session,
        tutor_user_id=tutor_user_id,
        student_id=lesson.student_id,
    )
    if student is None:
        raise StudentNotFoundError(f"Student {lesson.student_id} not found for lesson {lesson.id}")
    return student


def _resolve_duration_min(command: ConfirmLesson, lesson: TutoringLesson) -> int:
    """
    Priority:
    1) dto.actual_duration_min
    2) dto.actual_start_at + dto.actual_end_at
    3) planned lesson start/end
    """
    if command.actual_duration_min is not None:
        if command.actual_duration_min < 0:
            raise InvalidConfirmPayloadError("actual_duration_min must be >= 0")
        return command.actual_duration_min

    if command.actual_start_at and command.actual_end_at:
        try:
            return _duration_minutes_floor(command.actual_start_at, command.actual_end_at)
        except Exception as e:
            raise InvalidConfirmPayloadError("actual_end_at must be > actual_start_at") from e

    try:
        return _duration_minutes_floor(lesson.start_at, lesson.end_at)
    except Exception as e:
        raise InvalidConfirmPayloadError("lesson.end_at must be > lesson.start_at") from e


def _pick_base_rate(
        *,
        override_rate: Decimal | None,
        student: TutoringStudent | None,
        planned_rate_snapshot: Decimal | None,
) -> Decimal | None:
    if override_rate is not None:
        return override_rate
    if student is not None and student.default_rate is not None:
        return student.default_rate
    return planned_rate_snapshot


def _compute_charge(
        *,
        status: LessonStatus,
        duration_min: int,
        base_rate: Decimal | None,
        student: TutoringStudent | None,
) -> Decimal | None:
    # If a lesson did not take place: default 0.00
    if status in (LessonStatus.CANCELED, LessonStatus.NO_SHOW):
        return Decimal("0.00")

    if base_rate is None:
        return None

    if student is not None:
        return _calc_charge_amount(student=student, duration_min=duration_min, rate=base_rate)

    # Student unknown: simple per-hour calc without rounding policy
    hours = Decimal(duration_min) / Decimal(60)
    return _money(base_rate * hours)


# ============================================================
# Service
# ============================================================

async def confirm_lesson(
        session: AsyncSession,
        *,
        command: ConfirmLesson,
        allow_update_confirmed: bool = False,
) -> ConfirmLessonResult:
    """
    Confirm a lesson outcome and compute the actual charge.

    Notes:
    - No transactions/commit here. Caller controls transaction boundaries.
    - Idempotency: if a lesson is already CONFIRMED and allow_update_confirmed=False -> raises.
      If allow_update_confirmed=True -> overwrites actual fields (use carefully in admin UI).
    """
    lesson = await get_lesson_by_id(
        session,
        tutor_user_id=command.tutor_user_id,
        lesson_id=command.lesson_id,
    )
    if lesson is None:
        raise LessonNotFoundError(f"Lesson {command.lesson_id} not found")

    _ensure_can_confirm(lesson, allow_update_confirmed=allow_update_confirmed)

    student = await _load_student_or_raise(
        session,
        tutor_user_id=command.tutor_user_id,
        lesson=lesson,
    )

    # outcome
    lesson.status = command.status
    lesson.exception_code = command.exception_code
    lesson.exception_note = command.exception_note

    # actual
    duration_min = _resolve_duration_min(command, lesson)
    lesson.actual_duration_min = duration_min
    lesson.actual_start_at = command.actual_start_at
    lesson.actual_end_at = command.actual_end_at

    # money snapshots
    base_rate = _pick_base_rate(
        override_rate=command.override_rate,
        student=student,
        planned_rate_snapshot=lesson.planned_rate_snapshot,
    )
    lesson.actual_rate_snapshot = base_rate
    lesson.actual_charge_amount = _compute_charge(
        status=command.status,
        duration_min=duration_min,
        base_rate=base_rate,
        student=student,
    )

    # finalize
    lesson.confirmation_status = LessonConfirmationStatus.CONFIRMED
    lesson.confirmed_at = utc_now()

    return ConfirmLessonResult(lesson=lesson, student=student)


