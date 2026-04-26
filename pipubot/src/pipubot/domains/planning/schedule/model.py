from __future__ import annotations

from datetime import date, datetime, time
from uuid import UUID

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Time
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base
from pipubot.domains.planning.enums.schedule import ScheduleType
from pipubot.domains.planning.shared.mixins import IdMixin, TimestampMixin
from pipubot.domains.planning.task.model import Task


class TaskSchedule(Base, IdMixin, TimestampMixin):
    __tablename__ = "planning_task_schedules"

    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("planning_tasks.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    schedule_type: Mapped[ScheduleType] = mapped_column(
        Enum(ScheduleType, name="planning_schedule_type_enum"),
        nullable=False,
        index=True,
    )

    interval_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weekdays: Mapped[list[int] | None] = mapped_column(ARRAY(Integer), nullable=True)
    day_of_month: Mapped[int | None] = mapped_column(Integer, nullable=True)

    time_of_day: Mapped[time | None] = mapped_column(Time(timezone=False), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)

    start_date: Mapped[date | None] = mapped_column(nullable=True)
    end_date: Mapped[date | None] = mapped_column(nullable=True)

    next_run_at: Mapped[datetime | None] = mapped_column(nullable=True, index=True)
    last_generated_at: Mapped[datetime | None] = mapped_column(nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    task: Mapped["Task"] = relationship(
        "Task",
        back_populates="schedule",
    )