from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy import JSON as SAJSON
from sqlalchemy.orm import Mapped, mapped_column

from core.src.db.base import Base
from core.src.enums.background_task_enums import BackgroundTaskType, RecurringTaskStatus
from core.src.shared.utils.time_helpers import utcnow


class RecurringTask(Base):
    __tablename__ = "recurring_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    task_type: Mapped[BackgroundTaskType] = mapped_column(
        SAEnum(BackgroundTaskType, native_enum=False, validate_strings=True, length=64),
        nullable=False,
        index=True,
    )

    status: Mapped[RecurringTaskStatus] = mapped_column(
        SAEnum(RecurringTaskStatus, native_enum=False, validate_strings=True, length=32),
        nullable=False,
        default=RecurringTaskStatus.ACTIVE,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    first_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    run_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_runs: Mapped[int | None] = mapped_column(Integer, nullable=True)

    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False)

    payload_template: Mapped[dict] = mapped_column(SAJSON, nullable=False, default=dict)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_recurring_tasks_status_next_run", "status", "next_run_at"),
        Index("ix_recurring_tasks_task_type_status", "task_type", "status"),
    )
