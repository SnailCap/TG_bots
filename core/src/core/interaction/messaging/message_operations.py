from __future__ import annotations

from typing import Any, Optional, Union

from telegram import InlineKeyboardMarkup

from core.interaction.contracts.messenger import Messenger


async def send_message(
        *,
        chat_id: Union[int, str],
        text: str,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
        parse_mode: Optional[str] = "HTML",
        messenger: Optional[Messenger] = None,
        **kwargs: Any,
):
    ms = messenger
    return await ms.send(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
        **kwargs,
    )


async def edit_message(
        *,
        chat_id: Union[int, str],
        message_id: int,
        text: str,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
        parse_mode: Optional[str] = "HTML",
        messenger: Optional[Messenger] = None,
        **kwargs: Any,
):
    ms = messenger
    return await ms.edit(
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
        **kwargs,
    )


async def send_or_edit(
        *,
        chat_id: Union[int, str],
        text: str,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
        parse_mode: Optional[str] = "HTML",
        message_id: Optional[int] = None,
        messenger: Optional[Messenger] = None,
        **kwargs: Any,
):
    ms = messenger
    return await ms.send_or_edit(
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
        **kwargs,
    )
