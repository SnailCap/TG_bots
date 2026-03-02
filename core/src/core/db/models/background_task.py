from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy import JSON as SAJSON
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base
from core.enums.background_task_enums import BackgroundTaskStatus, BackgroundTaskType
from core.shared.utils.time_helpers import utcnow


class BackgroundTask(Base):
    __tablename__ = "background_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    task_type: Mapped[BackgroundTaskType] = mapped_column(String(128), nullable=False, index=True)

    status: Mapped[BackgroundTaskStatus] = mapped_column(
        SAEnum(BackgroundTaskStatus, native_enum=False, validate_strings=True, length=32),
        nullable=False,
        default=BackgroundTaskStatus.PENDING,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    payload: Mapped[dict] = mapped_column(SAJSON, nullable=False)

    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    retries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=5, nullable=False)

    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    recurring_task_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("recurring_tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    __table_args__ = (
        Index("ix_background_tasks_status_run_at", "status", "run_at"),
        Index("ix_background_tasks_type_status", "task_type", "status"),
    )
