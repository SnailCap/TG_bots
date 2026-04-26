from __future__ import annotations

from typing import Any

from core.interaction.messaging import Responder


class ReplyPort:
    def __init__(
        self,
        *,
        messenger,
        chat_id: int,
        message_id: int,
    ) -> None:
        self._responder = Responder(
            messenger=messenger,
            chat_id=chat_id,
            message_id=message_id,
        )

    async def reply(self, text: str, reply_markup: Any = None, *, with_send: bool = False):
        return await self._responder.reply(text, reply_markup, with_send=with_send)

    async def send(self, text: str, reply_markup: Any = None):
        return await self._responder.reply(text, reply_markup, with_send=True)

    async def edit(self, text: str, reply_markup: Any = None):
        return await self._responder.reply(text, reply_markup, with_send=False)