from __future__ import annotations

import enum


class LessonStatus(str, enum.Enum):
    PLANNED = "planned"
    DONE = "done"
    CANCELED = "canceled"
    NO_SHOW = "no_show"


class PaymentMethod(str, enum.Enum):
    CASH = "cash"
    BANK_TRANSFER = "bank_transfer"
    CARD = "card"
    STRIPE = "stripe"
    OTHER = "other"