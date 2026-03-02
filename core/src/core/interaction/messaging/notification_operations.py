from __future__ import annotations

from typing import Any, Optional

from core.interaction.contracts.messenger import Messenger
from core.interaction.contracts.render_data import RenderData
from core.interaction.contracts.ui_builder import UiBuilder
from core.interaction.messaging.message_operations import send_or_edit


async def send_notification(
        name: str,
        *,
        ui: UiBuilder,
        messenger: Messenger,
        chat_id: int,
        message_id: Optional[int] = None,
        text_vars: Optional[dict] = None,
        kb_vars: Optional[dict] = None,
        parse_mode: Optional[str] = None,
        **extra: Any,
):
    notification = ui.build_notification(name)

    data = RenderData(
        chat_id=chat_id,
        message_id=message_id,
        text_vars=text_vars or {},
        kb_vars=kb_vars or {},
        parse_mode=parse_mode,
    )

    params = await notification.to_out_params(
        chat_id=data.chat_id,
        message_id=data.message_id,
        text_vars=data.text_vars,
        kb_vars=data.kb_vars,
        parse_mode=data.parse_mode,
        **extra,
    )

    return await send_or_edit(messenger=messenger, **params)
