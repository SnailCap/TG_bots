from __future__ import annotations

from sqlalchemy import insert, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from core.db.models.sent_notification import SentNotification


async def try_claim_notification(
    session: AsyncSession,
    *,
    dedupe_key: str,
) -> bool:
    """
    Atomically claim dedupe_key.
    True  -> first time, proceed with sending
    False -> already claimed earlier, skip
    """
    stmt = (
        insert(SentNotification)
        .values(dedupe_key=dedupe_key)
        .on_conflict_do_nothing(index_elements=[SentNotification.dedupe_key])
        .returning(SentNotification.id)
    )

    res = await session.execute(stmt)
    return res.first() is not None


async def fill_claimed_notification(
    session: AsyncSession,
    *,
    dedupe_key: str,
    recipient_user_id: int,
    channel: str,
    notification_type: str,
    payload_json: dict | None = None,
    source_type: str | None = None,
    source_id: int | None = None,
) -> None:
    """
    Fill audit fields for an already-claimed row.
    Safe to call after try_claim_notification() == True.
    Idempotent: if the row doesn't exist, does nothing.
    """
    stmt = (
        update(SentNotification)
        .where(SentNotification.dedupe_key == dedupe_key)
        .values(
            recipient_user_id=recipient_user_id,
            channel=channel,
            notification_type=notification_type,
            payload_json=payload_json,
            source_type=source_type,
            source_id=source_id,
        )
    )

    await session.execute(stmt)