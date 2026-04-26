from enum import StrEnum


class ActivityEventType(StrEnum):
    TASK_CREATED = "task_created"
    TASK_UPDATED = "task_updated"
    TASK_COMPLETED = "task_completed"
    TASK_REOPENED = "task_reopened"
    TASK_CANCELLED = "task_cancelled"
    TASK_ARCHIVED = "task_archived"

    OCCURRENCE_CREATED = "occurrence_created"
    OCCURRENCE_COMPLETED = "occurrence_completed"
    OCCURRENCE_SKIPPED = "occurrence_skipped"
    OCCURRENCE_EXPIRED = "occurrence_expired"

    SCHEDULE_CREATED = "schedule_created"
    SCHEDULE_UPDATED = "schedule_updated"
    SCHEDULE_DEACTIVATED = "schedule_deactivated"

    REMINDER_RULE_CREATED = "reminder_rule_created"
    REMINDER_SENT = "reminder_sent"
    REMINDER_FAILED = "reminder_failed"