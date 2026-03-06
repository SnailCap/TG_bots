from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from core.db.repositories.sent_notification_repository import (
    try_claim_notification,
    fill_claimed_notification,
)


@dataclass(slots=True, frozen=True)
class DbNotificationLog:
    async def try_claim(self, *, session: AsyncSession, dedupe_key: str) -> bool:
        return await try_claim_notification(session, dedupe_key=dedupe_key)

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
        await fill_claimed_notification(
            session,
            dedupe_key=dedupe_key,
            recipient_user_id=recipient_user_id,
            channel=channel,
            notification_type=notification_type,
            payload_json=payload,
            source_type=source_type,
            source_id=source_id,
        )