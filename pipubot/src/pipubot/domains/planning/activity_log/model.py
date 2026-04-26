from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Enum, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base
from pipubot.domains.planning.enums.activity import ActivityEventType
from pipubot.domains.planning.shared.mixins import IdMixin, TimestampMixin
from pipubot.domains.planning.occurrence.model import TaskOccurrence
from pipubot.domains.planning.task.model import Task


class TaskActivityLog(Base, IdMixin, TimestampMixin):
    __tablename__ = "planning_task_activity_logs"

    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("planning_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    occurrence_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("planning_task_occurrences.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    event_type: Mapped[ActivityEventType] = mapped_column(
        Enum(ActivityEventType, name="planning_activity_event_type_enum"),
        nullable=False,
        index=True,
    )

    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    task: Mapped["Task"] = relationship(
        "Task",
        back_populates="activity_logs",
    )

    occurrence: Mapped["TaskOccurrence | None"] = relationship(
        "TaskOccurrence",
        back_populates="activity_logs",
    )