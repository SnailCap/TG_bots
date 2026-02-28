from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base
from core.shared.utils.time_helpers import utcnow
from pipubot.domains.tutoring.models.mixins import TutoringOwnedMixin


class TutoringCalendarWatchChannel(TutoringOwnedMixin, Base):
    """
    Stores Google Calendar push notification (watch) channel data.
    Renew channels by creating new watch requests before expiration.
    """
    __tablename__ = "tutoring_calendar_watch_channels"

    id: Mapped[int] = mapped_column(primary_key=True)

    google_calendar_id: Mapped[str] = mapped_column(String(256), nullable=False)

    channel_id: Mapped[str] = mapped_column(String(256), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(256), nullable=False)

    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "tutor_user_id",
            "google_calendar_id",
            name="uq_tutoring_watch_tutor_calendar",
        ),
        Index("ix_tutoring_watch_tutor_expires", "tutor_user_id", "expires_at"),
    )