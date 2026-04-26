from __future__ import annotations

from sqlalchemy import Boolean, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid import UUID

from core.db.base import Base
from pipubot.domains.planning.enums.reminder import ReminderChannel, ReminderKind
from pipubot.domains.planning.shared.mixins import IdMixin, TimestampMixin
from pipubot.domains.planning.task.model import Task
from pipubot.domains.planning.reminder_dispatch.model import ReminderDispatch


class ReminderRule(Base, IdMixin, TimestampMixin):
    __tablename__ = "planning_reminder_rules"

    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("planning_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    kind: Mapped[ReminderKind] = mapped_column(
        Enum(ReminderKind, name="planning_reminder_kind_enum"),
        nullable=False,
        index=True,
    )

    channel: Mapped[ReminderChannel] = mapped_column(
        Enum(ReminderChannel, name="planning_reminder_channel_enum"),
        nullable=False,
        default=ReminderChannel.TELEGRAM,
    )

    offset_minutes: Mapped[int | None] = mapped_column(nullable=True)
    repeat_interval_minutes: Mapped[int | None] = mapped_column(nullable=True)
    max_repeat_count: Mapped[int | None] = mapped_column(nullable=True)

    inactivity_threshold_minutes: Mapped[int | None] = mapped_column(nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    task: Mapped["Task"] = relationship(
        "Task",
        back_populates="reminder_rules",
    )

    dispatches: Mapped[list["ReminderDispatch"]] = relationship(
        "ReminderDispatch",
        back_populates="rule",
        cascade="all, delete-orphan",
    )