from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base
from core.shared.utils.time import utc_now


class HelperTextPreset(Base):
    __tablename__ = "helper_text_presets"

    id: Mapped[int] = mapped_column(primary_key=True)

    owner_telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    text: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_text: Mapped[str] = mapped_column(String(255), nullable=False)
    base_length: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    bottom_extra_symbols: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "owner_telegram_id",
            "normalized_text",
            name="uq_helper_text_presets_owner_normalized_text",
        ),
        Index(
            "ix_helper_text_presets_owner_updated",
            "owner_telegram_id",
            "updated_at",
        ),
        CheckConstraint("base_length > 0", name="ck_helper_text_presets_base_length_positive"),
    )
