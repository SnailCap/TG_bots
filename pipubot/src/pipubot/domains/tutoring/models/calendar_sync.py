from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base
from core.shared.utils.time_helpers import utcnow
from pipubot.domains.tutoring.models.mixins import TutoringOwnedMixin


class TutoringCalendarSyncState(TutoringOwnedMixin, Base):
    """
    Stores incremental sync state (syncToken) per tutor and per calendar.
    """
    __tablename__ = "tutoring_calendar_sync_state"

    id: Mapped[int] = mapped_column(primary_key=True)

    google_calendar_id: Mapped[str] = mapped_column(String(256), nullable=False)

    sync_token: Mapped[str | None] = mapped_column(String(2048))

    # materialize instances for N days ahead
    window_days: Mapped[int] = mapped_column(default=45, nullable=False)

    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "tutor_user_id",
            "google_calendar_id",
            name="uq_tutoring_calendar_sync_state_tutor_calendar",
        ),
    )