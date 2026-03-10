from __future__ import annotations

from enum import Enum


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
