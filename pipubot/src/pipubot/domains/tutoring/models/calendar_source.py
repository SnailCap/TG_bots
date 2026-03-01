from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base
from core.shared.utils.time_helpers import utcnow
from pipubot.domains.tutoring.models.mixins import TutoringOwnedMixin


class TutoringCalendarSource(TutoringOwnedMixin, Base):
    """
    Per-tutor calendar sync state.

    - sync_token is used for incremental sync (events.list with syncToken)
    - last_synced_at is your own bookkeeping (observability)
    - window_days stores the horizon you materialize locally (optional)
    """

    __tablename__ = "tutoring_calendar_sources"

    id: Mapped[int] = mapped_column(primary_key=True)

    calendar_id: Mapped[str] = mapped_column(String(256), nullable=False)

    sync_token: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    window_days: Mapped[int] = mapped_column(Integer, default=60, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("tutor_user_id", "calendar_id", name="uq_tutoring_calendar_source"),
        Index("ix_tutoring_calendar_source_tutor_updated", "tutor_user_id", "updated_at"),
    )