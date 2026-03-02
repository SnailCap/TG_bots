from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from core.shared.utils.time_helpers import utcnow
from pipubot.domains.tutoring.models.enums import (
    BillingChargeModel,
    LessonConfirmationStatus,
    LessonExceptionCode,
    LessonStatus,
)
from pipubot.domains.tutoring.models.lesson import TutoringLesson
from pipubot.domains.tutoring.models.student import TutoringStudent
from pipubot.domains.tutoring.repositories.lesson_repository import get_lesson_by_id
from pipubot.domains.tutoring.repositories.student_repository import get_student_by_id
from pipubot.domains.tutoring.utils.time.time_range import TimeRange
from pipubot.domains.tutoring.utils.time.time_rounding import round_minutes
from pipubot.domains.tutoring.errors.errors import (
    LessonNotFoundError,
    StudentNotFoundError,
    LessonAlreadyConfirmedError,
    InvalidConfirmPayloadError,
)


# ============================================================
# DTOs
# ============================================================

@dataclass(frozen=True, slots=True)
class ConfirmLessonDTO:
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


@dataclass(frozen=True, slots=True)
class ConfirmLessonResult:
    lesson: TutoringLesson
    student: Optional[TutoringStudent]


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
    bill_min = round_minutes(bill_min, student.rounding_minutes, student.rounding_mode)

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


def _resolve_duration_min(dto: ConfirmLessonDTO, lesson: TutoringLesson) -> int:
    """
    Priority:
    1) dto.actual_duration_min
    2) dto.actual_start_at + dto.actual_end_at
    3) planned lesson start/end
    """
    if dto.actual_duration_min is not None:
        if dto.actual_duration_min < 0:
            raise InvalidConfirmPayloadError("actual_duration_min must be >= 0")
        return dto.actual_duration_min

    if dto.actual_start_at and dto.actual_end_at:
        try:
            return TimeRange(dto.actual_start_at, dto.actual_end_at).duration_minutes_floor
        except Exception as e:
            # keep error type stable for callers
            raise InvalidConfirmPayloadError("actual_end_at must be > actual_start_at") from e

    return TimeRange(lesson.start_at, lesson.end_at).duration_minutes_floor


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
    dto: ConfirmLessonDTO,
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
        tutor_user_id=dto.tutor_user_id,
        lesson_id=dto.lesson_id,
    )
    if lesson is None:
        raise LessonNotFoundError(f"Lesson {dto.lesson_id} not found")

    _ensure_can_confirm(lesson, allow_update_confirmed=allow_update_confirmed)

    student = await _load_student_or_raise(
        session,
        tutor_user_id=dto.tutor_user_id,
        lesson=lesson,
    )

    # outcome
    lesson.status = dto.status
    lesson.exception_code = dto.exception_code
    lesson.exception_note = dto.exception_note

    # actual
    duration_min = _resolve_duration_min(dto, lesson)
    lesson.actual_duration_min = duration_min
    lesson.actual_start_at = dto.actual_start_at
    lesson.actual_end_at = dto.actual_end_at

    # money snapshots
    base_rate = _pick_base_rate(
        override_rate=dto.override_rate,
        student=student,
        planned_rate_snapshot=lesson.planned_rate_snapshot,
    )
    lesson.actual_rate_snapshot = base_rate
    lesson.actual_charge_amount = _compute_charge(
        status=dto.status,
        duration_min=duration_min,
        base_rate=base_rate,
        student=student,
    )

    # finalize
    lesson.confirmation_status = LessonConfirmationStatus.CONFIRMED
    lesson.confirmed_at = utcnow()

    return ConfirmLessonResult(lesson=lesson, student=student)