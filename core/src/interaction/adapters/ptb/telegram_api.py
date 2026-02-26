from __future__ import annotations

from typing import Optional, Union, Any

from telegram import Bot, InlineKeyboardMarkup


# This module is intentionally LOW-LEVEL.
# It must NOT import FactoryHub / NotificationFactory / RenderData / repositories / services.
# Only thin wrappers over Bot methods + bot lifecycle (set_bot / require_bot).


_BOT: Optional[Bot] = None


def set_bot(bot: Bot) -> None:
    """
    Initialize the global Bot instance for the current process.
    Call once early during app startup (e.g. EKApp.__init__ or post_init).
    """
    global _BOT
    _BOT = bot


def require_bot() -> Bot:
    """
    Get the initialized Bot instance or raise a clear error.
    """
    if _BOT is None:
        raise RuntimeError(
            "Telegram Bot is not initialized. Call set_bot(app.bot) early "
            "(e.g., in EKApp.__init__ / post_init) before using telegram_api."
        )
    return _BOT


# -------------------------
# Raw Telegram API wrappers
# -------------------------

async def send_message(
    chat_id: Union[int, str],
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: Optional[str] = "HTML",
    **kwargs: Any,
):
    """
    Thin wrapper over Bot.send_message.
    Pass-through kwargs are allowed for Telegram API options (disable_web_page_preview, etc.).
    """
    bot = require_bot()
    return await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
        **kwargs,
    )


async def edit_message_text(
    chat_id: Union[int, str],
    message_id: int,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: Optional[str] = "HTML",
    **kwargs: Any,
):
    """
    Thin wrapper over Bot.edit_message_text.
    """
    bot = require_bot()
    return await bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
        **kwargs,
    )


async def create_chat_invite_link(
    chat_id: Union[int, str],
    **kwargs: Any,
):
    """
    Thin wrapper over Bot.create_chat_invite_link.
    Accepts all native kwargs: name, expire_date, member_limit, creates_join_request, etc.
    """
    bot = require_bot()
    return await bot.create_chat_invite_link(chat_id=chat_id, **kwargs)


async def revoke_chat_invite_link(
    chat_id: Union[int, str],
    invite_link: str,
):
    """
    Thin wrapper over Bot.revoke_chat_invite_link.
    """
    bot = require_bot()
    return await bot.revoke_chat_invite_link(chat_id=chat_id, invite_link=invite_link)
