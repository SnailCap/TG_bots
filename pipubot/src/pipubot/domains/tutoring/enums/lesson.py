from __future__ import annotations

from enum import Enum


class LessonStatus(str, Enum):
    """
    High-level lesson lifecycle status.

    PLANNED: imported/planned from calendar, not confirmed yet.
    DONE: a lesson took place.
    CANCELED: canceled (by tutor/student) and did not take place.
    NO_SHOW: did not take place because a student didn't show up (or agreed definition).
    """
    PLANNED = "planned"
    DONE = "done"
    CANCELED = "canceled"
    NO_SHOW = "no_show"


class LessonConfirmationStatus(str, Enum):
    """
    Confirmation is about YOUR bookkeeping decision (post-lesson).

    PENDING: waiting for your input.
    CONFIRMED: you confirmed outcome/actual and the charge is final.
    """
    PENDING = "pending"
    CONFIRMED = "confirmed"


class LessonExceptionCode(str, Enum):
    """
    Structured reasons why actual differs from planned (optional).
    Useful for 1-click UI buttons and analytics.
    """
    NONE = "none"

    # timing
    STUDENT_LATE = "student_late"
    TUTOR_LATE = "tutor_late"
    SHORTENED = "shortened"
    EXTENDED = "extended"

    # billing adjustments
    DISCOUNT = "discount"
    FREE = "free"
    EXTRA_CHARGE = "extra_charge"

    # policy-based outcomes
    LATE_CANCEL_FEE = "late_cancel_fee"
    NO_SHOW_FEE = "no_show_fee"
    MAKEUP = "makeup"  # e.g., compensation lesson
