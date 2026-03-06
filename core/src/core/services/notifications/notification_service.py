from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from core.interaction.contracts.messenger import Messenger
from core.interaction.contracts.ui_builder import UiBuilder
from core.interaction.messaging import send_or_edit_message
from core.services.notifications.contracts.notification_log import NotificationLog
from core.services.notifications.types import NotificationSource


@dataclass(slots=True, frozen=True)
class NotificationService:
    ui: UiBuilder
    messenger: Messenger
    default_parse_mode: Optional[str] = "HTML"
    notification_log: NotificationLog | None = None

    async def send(
        self,
        notification_key: str,
        *,
        chat_id: int,
        session: AsyncSession | None = None,
        message_id: Optional[int] = None,
        text_vars: Optional[dict[str, Any]] = None,
        kb_vars: Optional[dict[str, Any]] = None,
        parse_mode: Optional[str] = None,
        dedupe_key: str | None = None,
        notification_type: str | None = None,
        channel: str = "telegram",
        payload: dict | None = None,
        source: NotificationSource | None = None,
        **extra: Any,
    ) -> Any:
        should_log = self._should_log(dedupe_key)

        if should_log:
            session = self._require_session(session)
            if not await self.notification_log.try_claim(session=session, dedupe_key=dedupe_key):  # type: ignore[union-attr]
                return None

        notif_obj = self.ui.build_notification(notification_key)
        resolved_parse_mode = self._resolve_parse_mode(notif_obj, parse_mode)

        params = await notif_obj.to_out_params(
            chat_id=chat_id,
            message_id=message_id,
            text_vars=text_vars or {},
            kb_vars=kb_vars or {},
            parse_mode=resolved_parse_mode,
            **extra,
        )

        result = await send_or_edit_message(messenger=self.messenger, **params)

        if should_log:
            assert session is not None
            await self.notification_log.record_sent(  # type: ignore[union-attr]
                session=session,
                dedupe_key=dedupe_key,  # type: ignore[arg-type]
                recipient_user_id=chat_id,
                notification_type=notification_type or notification_key,
                channel=channel,
                payload=payload,
                source_type=self._source_type(source),
                source_id=self._source_id(source),
            )

        return result

    def _should_log(self, dedupe_key: str | None) -> bool:
        return bool(dedupe_key) and self.notification_log is not None

    def _require_session(self, session: AsyncSession | None) -> AsyncSession:
        if session is None:
            raise TypeError(
                "NotificationService.send: `session` is required when `dedupe_key` is provided "
                "and notification_log is enabled."
            )
        return session

    def _resolve_parse_mode(self, notif_obj: Any, parse_mode: Optional[str]) -> Optional[str]:
        return parse_mode or getattr(notif_obj, "_parse_mode", None) or self.default_parse_mode

    def _source_type(self, source: NotificationSource | None) -> str | None:
        return source.type if source else None

    def _source_id(self, source: NotificationSource | None) -> int | None:
        return source.id if source else None