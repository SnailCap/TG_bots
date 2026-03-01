from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base
from core.shared.utils.time_helpers import utcnow


class TutoringCalendarEventMap(Base):
    """
    Maps Google event instance -> local lesson.
    Important for recurring instances: instance_id changes per occurrence.
    """
    __tablename__ = "tutoring_calendar_event_map"
    __table_args__ = (
        UniqueConstraint("tutor_user_id", "calendar_id", "google_event_id", name="uq_tut_evt_map"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    tutor_user_id: Mapped[int] = mapped_column(index=True, nullable=False)
    calendar_id: Mapped[str] = mapped_column(String(256), nullable=False)

    # Google event id of the instance returned by events.list(singleEvents=true)
    google_event_id: Mapped[str] = mapped_column(String(256), nullable=False)

    # Helpful extra identity (optional, but nice for debugging / edge cases)
    ical_uid: Mapped[str | None] = mapped_column(String(256), nullable=True)
    recurring_event_id: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # FK-less by design (you can add FK later if you want)
    lesson_id: Mapped[int] = mapped_column(index=True, nullable=False)

    # Track last seen event payload version
    google_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )