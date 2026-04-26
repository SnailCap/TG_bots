from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base
from pipubot.domains.planning.enums.reminder import ReminderStatus
from pipubot.domains.planning.shared.mixins import IdMixin, TimestampMixin
from pipubot.domains.planning.occurrence.model import TaskOccurrence
from pipubot.domains.planning.reminder_rule.model import ReminderRule


class ReminderDispatch(Base, IdMixin, TimestampMixin):
    __tablename__ = "planning_reminder_dispatches"

    rule_id: Mapped[UUID] = mapped_column(
        ForeignKey("planning_reminder_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("planning_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    occurrence_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("planning_task_occurrences.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    planned_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(nullable=True)

    status: Mapped[ReminderStatus] = mapped_column(
        Enum(ReminderStatus, name="planning_reminder_status_enum"),
        nullable=False,
        default=ReminderStatus.PENDING,
        index=True,
    )

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    rule: Mapped["ReminderRule"] = relationship(
        "ReminderRule",
        back_populates="dispatches",
    )

    occurrence: Mapped["TaskOccurrence | None"] = relationship(
        "TaskOccurrence",
        back_populates="reminder_dispatches",
    )