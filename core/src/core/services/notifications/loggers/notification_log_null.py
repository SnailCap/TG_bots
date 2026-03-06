# core/services/notifications/loggers/null_notification_log.py
from __future__ import annotations


class NullNotificationLog:
    async def try_claim(self, *, dedupe_key: str) -> bool:
        return True

    async def record_sent(
            self,
            *,
            dedupe_key: str,
            recipient_user_id: int,
            notification_type: str,
            channel: str,
            payload: dict | None = None,
            source_type: str | None = None,
            source_id: int | None = None,
    ) -> None:
        return
