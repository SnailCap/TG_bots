from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, overload, Union

from core.interaction.contracts.messenger import Messenger
from core.interaction.contracts.ui_builder import UiBuilder
from core.interaction.messaging import send_or_edit_message
from core.interaction.ui.components.notification.base_notification import Notification


NotificationInput = Union[Notification, str]


@dataclass(slots=True, frozen=True)
class NotificationService:
    ui: UiBuilder
    messenger: Messenger
    default_parse_mode: Optional[str] = "HTML"

    @overload
    async def send(
        self,
        notification: Notification,
        *,
        chat_id: int,
        message_id: Optional[int] = None,
        text_vars: Optional[dict[str, Any]] = None,
        kb_vars: Optional[dict[str, Any]] = None,
        parse_mode: Optional[str] = None,
        **extra: Any,
    ) -> Any: ...

    @overload
    async def send(
        self,
        notification: str,
        *,
        chat_id: int,
        message_id: Optional[int] = None,
        text_vars: Optional[dict[str, Any]] = None,
        kb_vars: Optional[dict[str, Any]] = None,
        parse_mode: Optional[str] = None,
        **extra: Any,
    ) -> Any: ...

    async def send(
        self,
        notification: NotificationInput,
        *,
        chat_id: int,
        message_id: Optional[int] = None,
        text_vars: Optional[dict[str, Any]] = None,
        kb_vars: Optional[dict[str, Any]] = None,
        parse_mode: Optional[str] = None,
        **extra: Any,
    ) -> Any:
        if isinstance(notification, str):
            notif_obj = self.ui.build_notification(notification)
        else:
            notif_obj = notification

        resolved_parse_mode = (
            parse_mode
            or getattr(notif_obj, "_parse_mode", None)
            or self.default_parse_mode
        )

        params = await notif_obj.to_out_params(
            chat_id=chat_id,
            message_id=message_id,
            text_vars=text_vars or {},
            kb_vars=kb_vars or {},
            parse_mode=resolved_parse_mode,
            **extra,
        )

        return await send_or_edit_message(
            messenger=self.messenger,
            **params,
        )