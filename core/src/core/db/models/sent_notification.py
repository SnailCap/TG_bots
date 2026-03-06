from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base


class SentNotification(Base):
    """
    Universal log of notifications (used for idempotency + optional audit/debug).
    """

    __tablename__ = "sent_notifications"

    id: Mapped[int] = mapped_column(primary_key=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Who received it (e.g. Telegram chat_id / user id). Optional for "claim-only" row.
    recipient_user_id: Mapped[int | None] = mapped_column(index=True, nullable=True)

    # "telegram", "email", ...
    channel: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # "lesson_reminder", "payment_receipt", ...
    notification_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # Idempotency key. Must always be present.
    dedupe_key: Mapped[str] = mapped_column(String(255), nullable=False)

    # Optional linkage to a domain entity
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Snapshot of what was sent (optional, great for debugging)
    payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_sent_notifications_dedupe_key"),
        Index("ix_sent_notifications_related", "source_type", "source_id"),
    )
