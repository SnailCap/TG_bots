from __future__ import annotations

from typing import Any, Optional

from telegram import Bot
from telegram.error import BadRequest

from core.interaction.contracts.messenger import ChatId, Messenger

_EDIT_FALLBACK_SUBSTRINGS: tuple[str, ...] = (
    "message to edit not found",
    "message can't be edited",
    "Message to edit not found",
    "Message can't be edited",
)

_NOOP_EDIT_SUBSTRINGS: tuple[str, ...] = (
    # PTB/Telegram sometimes differs by case; keep both to be safe
    "message is not modified",
    "Message is not modified",
    # sometimes this longer text appears exactly as in your traceback
    "specified new message content and reply markup are exactly the same",
)

def _should_fallback_to_send(err: BadRequest) -> bool:
    msg = str(err)
    return any(s in msg for s in _EDIT_FALLBACK_SUBSTRINGS)

def _should_noop_on_edit(err: BadRequest) -> bool:
    msg = str(err)
    return any(s in msg for s in _NOOP_EDIT_SUBSTRINGS)


class PtbMessenger:
    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def send(
        self,
        *,
        chat_id: ChatId,
        text: str,
        reply_markup: Optional[Any] = None,
        parse_mode: Optional[str] = "HTML",
        **kwargs: Any,
    ) -> Any:
        return await self._bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            **kwargs,
        )

    async def edit(
        self,
        *,
        chat_id: ChatId,
        message_id: int,
        text: str,
        reply_markup: Optional[Any] = None,
        parse_mode: Optional[str] = "HTML",
        **kwargs: Any,
    ) -> Any:
        return await self._bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            **kwargs,
        )

    async def send_or_edit(
        self,
        *,
        chat_id: ChatId,
        text: str,
        reply_markup: Optional[Any] = None,
        parse_mode: Optional[str] = "HTML",
        message_id: Optional[int] = None,
        **kwargs: Any,
    ) -> Any:
        if message_id is None:
            return await self.send(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                **kwargs,
            )

        try:
            return await self.edit(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                **kwargs,
            )
        except BadRequest as e:
            if _should_noop_on_edit(e):
                return None

            if _should_fallback_to_send(e):
                return await self.send(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                    **kwargs,
                )
            raise