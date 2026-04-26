from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base
from pipubot.domains.planning.enums.occurrence import OccurrenceStatus
from pipubot.domains.planning.shared.mixins import IdMixin, TimestampMixin
from pipubot.domains.planning.task.model import Task
from pipubot.domains.planning.activity_log.model import TaskActivityLog
from pipubot.domains.planning.reminder_dispatch.model import ReminderDispatch


class TaskOccurrence(Base, IdMixin, TimestampMixin):
    __tablename__ = "planning_task_occurrences"

    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("planning_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    scheduled_at: Mapped[datetime | None] = mapped_column(nullable=True, index=True)
    due_at: Mapped[datetime | None] = mapped_column(nullable=True, index=True)

    status: Mapped[OccurrenceStatus] = mapped_column(
        Enum(OccurrenceStatus, name="planning_occurrence_status_enum"),
        nullable=False,
        default=OccurrenceStatus.PENDING,
        index=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    skipped_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_progress_at: Mapped[datetime | None] = mapped_column(nullable=True)
    snoozed_until: Mapped[datetime | None] = mapped_column(nullable=True)

    task: Mapped["Task"] = relationship(
        "Task",
        back_populates="occurrences",
    )

    reminder_dispatches: Mapped[list["ReminderDispatch"]] = relationship(
        "ReminderDispatch",
        back_populates="occurrence",
        cascade="all, delete-orphan",
    )

    activity_logs: Mapped[list["TaskActivityLog"]] = relationship(
        "TaskActivityLog",
        back_populates="occurrence",
    )