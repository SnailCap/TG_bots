from enum import StrEnum


class ScheduleType(StrEnum):
    ONCE = "once"
    INTERVAL = "interval"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CRON_LIKE = "cron_like"