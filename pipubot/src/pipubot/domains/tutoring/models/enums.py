# pipubot/domains/tutoring/models/enums.py
from __future__ import annotations

import enum


class LessonStatus(str, enum.Enum):
    """
    High-level lesson lifecycle status.

    PLANNED: imported/planned from calendar, not confirmed yet.
    DONE: lesson took place.
    CANCELED: canceled (by tutor/student) and did not take place.
    NO_SHOW: did not take place because student didn't show up (or agreed definition).
    """
    PLANNED = "planned"
    DONE = "done"
    CANCELED = "canceled"
    NO_SHOW = "no_show"


class LessonConfirmationStatus(str, enum.Enum):
    """
    Confirmation is about YOUR bookkeeping decision (post-lesson).

    PENDING: waiting for your input.
    CONFIRMED: you confirmed outcome/actuals and the charge is final.
    """
    PENDING = "pending"
    CONFIRMED = "confirmed"


class LessonExceptionCode(str, enum.Enum):
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
    MAKEUP = "makeup"  # e.g. compensation lesson


class BillingChargeModel(str, enum.Enum):
    """
    How the lesson charge is computed.
    """
    FIXED = "fixed"               # fixed price per lesson
    PER_HOUR = "per_hour"         # price per hour with rounding
    PER_MINUTE = "per_minute"     # price per minute (rare, but future-proof)


class RoundingMode(str, enum.Enum):
    """
    How to round computed minutes for billing.
    """
    NONE = "none"
    UP = "up"
    DOWN = "down"
    NEAREST = "nearest"


class PaymentMethod(str, enum.Enum):
    CASH = "cash"
    BANK_TRANSFER = "bank_transfer"
    CARD = "card"
    STRIPE = "stripe"
    OTHER = "other"