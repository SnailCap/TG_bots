from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column


class TutoringOwnedMixin:
    """
    Multi-tenant scope for tutoring domain.

    In your project, User PK is users.telegram_id (BigInteger).
    Every tutoring entity must be scoped by tutor_user_id = users.telegram_id.
    """

    tutor_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )