from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base
from pipubot.domains.planning.enums.task import TaskStatus, TaskPriority, TaskKind
from pipubot.domains.planning.shared.mixins import IdMixin, TimestampMixin
from pipubot.domains.planning.occurrence.model import TaskOccurrence
from pipubot.domains.planning.reminder_rule.model import ReminderRule
from pipubot.domains.planning.schedule.model import TaskSchedule
from pipubot.domains.planning.activity_log.model import TaskActivityLog


class Task(Base, IdMixin, TimestampMixin):
    __tablename__ = "planning_tasks"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.telegram_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="planning_task_status_enum"),
        nullable=False,
        default=TaskStatus.PENDING,
        index=True,
    )

    priority: Mapped[TaskPriority] = mapped_column(
        Enum(TaskPriority, name="planning_task_priority_enum"),
        nullable=False,
        default=TaskPriority.MEDIUM,
        index=True,
    )

    kind: Mapped[TaskKind] = mapped_column(
        Enum(TaskKind, name="planning_task_kind_enum"),
        nullable=False,
        default=TaskKind.ONE_TIME,
        index=True,
    )

    start_at: Mapped[datetime | None] = mapped_column(nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(nullable=True)
    scheduled_for: Mapped[datetime | None] = mapped_column(nullable=True)

    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_progress_at: Mapped[datetime | None] = mapped_column(nullable=True)
    snoozed_until: Mapped[datetime | None] = mapped_column(nullable=True)

    parent_task_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("planning_tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)

    parent_task: Mapped["Task | None"] = relationship(
        "Task",
        remote_side="Task.id",
        back_populates="subtasks",
    )
    subtasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="parent_task",
    )

    schedule: Mapped["TaskSchedule | None"] = relationship(
        "TaskSchedule",
        back_populates="task",
        uselist=False,
        cascade="all, delete-orphan",
    )

    occurrences: Mapped[list["TaskOccurrence"]] = relationship(
        "TaskOccurrence",
        back_populates="task",
        cascade="all, delete-orphan",
    )

    reminder_rules: Mapped[list["ReminderRule"]] = relationship(
        "ReminderRule",
        back_populates="task",
        cascade="all, delete-orphan",
    )

    activity_logs: Mapped[list["TaskActivityLog"]] = relationship(
        "TaskActivityLog",
        back_populates="task",
        cascade="all, delete-orphan",
    )
