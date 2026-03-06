from __future__ import annotations

from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession


class NotificationLog(Protocol):
    async def try_claim(self, *, session: AsyncSession, dedupe_key: str) -> bool:
        """
        Atomic idempotency gate.
        True  -> proceed with sending (first time)
        False -> already claimed/sent earlier, skip
        """

    async def record_sent(
        self,
        *,
        session: AsyncSession,
        dedupe_key: str,
        recipient_user_id: int,
        notification_type: str,
        channel: str,
        payload: dict | None = None,
        source_type: str | None = None,
        source_id: int | None = None,
    ) -> None:
        """
        Optional: store details/audit.
        For Null logger it's no-op.
        """