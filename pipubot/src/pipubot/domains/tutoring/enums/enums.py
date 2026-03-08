# pipubot/domains/tutoring/models/enums.py
from __future__ import annotations

from enum import Enum, StrEnum


class CalendarSourceStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    REAUTH_REQUIRED = "reauth_required"

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


class BillingChargeModel(str, Enum):
    """
    How the lesson charge is computed.
    """
    FIXED = "fixed"               # fixed price per lesson
    PER_HOUR = "per_hour"         # price per hour with rounding
    PER_MINUTE = "per_minute"     # price per minute (rare, but future-proof)


class RoundingMode(str, Enum):
    """
    How to round computed minutes for billing.
    """
    NONE = "none"
    UP = "up"
    DOWN = "down"
    NEAREST = "nearest"


class PaymentMethod(str, Enum):
    CASH = "cash"
    BANK_TRANSFER = "bank_transfer"
    CARD = "card"
    STRIPE = "stripe"
    OTHER = "other"

class StudentState(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    INACTIVE = "INACTIVE"


class SchoolGrade(str, Enum):
    GRADE_1 = "GRADE_1"
    GRADE_2 = "GRADE_2"
    GRADE_3 = "GRADE_3"
    GRADE_4 = "GRADE_4"
    GRADE_5 = "GRADE_5"
    GRADE_6 = "GRADE_6"
    GRADE_7 = "GRADE_7"
    GRADE_8 = "GRADE_8"
    GRADE_9 = "GRADE_9"
    GRADE_10 = "GRADE_10"
    GRADE_11 = "GRADE_11"
    GRADE_12 = "GRADE_12"
    ADULT = "ADULT"
    ADMISSION = "ADMISSION"


class ExamTrack(str, Enum):
    WIDE = "WIDE"
    NARROW = "NARROW"
    BASIC_9 = "BASIC_9"
    ADMISSION_TEST = "ADMISSION_TEST"


class StudyLanguage(str, Enum):
    RUSSIAN = "RUSSIAN"
    ESTONIAN = "ESTONIAN"
    ENGLISH = "ENGLISH"


class StudyFormat(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    HYBRID = "HYBRID"


class PaymentAccount(str, Enum):
    KONSTANTIN_SWEDBANK = "KONSTANTIN_SWEDBANK"
    KONSTANTIN_REVOLUT = "KONSTANTIN_REVOLUT"
    DIANA_KISS = "DIANA_KISS"
    ALJONA_BUKATY = "ALJONA_BUKATY"
