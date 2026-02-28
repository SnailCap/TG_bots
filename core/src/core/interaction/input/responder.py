from __future__ import annotations

from typing import Any, Optional

from core.interaction.contracts.messenger import Messenger


class Responder:
    """
    UI delivery policy (send vs. edit) that depends on the current telegram 'anchor' message.
    """

    def __init__(self, *, messenger: Messenger, chat_id: int, message_id: int) -> None:
        self._messenger = messenger
        self._chat_id = chat_id
        # message_id==0 means "no anchor", treat it like None.
        self._message_id: Optional[int] = message_id or None

    async def reply(self, text: str, reply_markup: Any = None, *, with_send: bool = False):
        if with_send or self._message_id is None:
            return await self._messenger.send(
                chat_id=self._chat_id,
                text=text,
                reply_markup=reply_markup,
            )

        return await self._messenger.send_or_edit(
            chat_id=self._chat_id,
            message_id=self._message_id,
            text=text,
            reply_markup=reply_markup,
        )