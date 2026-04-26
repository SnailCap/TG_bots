from enum import StrEnum


class ReminderKind(StrEnum):
    BEFORE_DUE = "before_due"
    AFTER_DUE = "after_due"
    ON_START = "on_start"
    ON_SCHEDULED_TIME = "on_scheduled_time"
    INACTIVITY = "inactivity"


class ReminderStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReminderChannel(StrEnum):
    TELEGRAM = "telegram"
    INTERNAL = "internal"
    EMAIL = "email"


class ReminderTargetType(StrEnum):
    TASK = "task"
    OCCURRENCE = "occurrence"