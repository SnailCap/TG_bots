from __future__ import annotations

from telegram import Bot
from telegram.error import InvalidToken, TelegramError

from app.domain.project import BotIdentity
from app.errors import TokenValidationError


class PtbBotTokenValidator:
    async def validate(self, token: str) -> BotIdentity:
        normalized = token.strip()
        if not normalized:
            raise TokenValidationError("Telegram token must not be empty")
        try:
            async with Bot(normalized) as bot:
                user = await bot.get_me()
        except (InvalidToken, TelegramError) as exc:
            raise TokenValidationError(
                f"Telegram token validation failed: {exc}"
            ) from exc

        display_name = " ".join(
            part for part in (user.first_name, user.last_name) if part
        ).strip()
        return BotIdentity(
            bot_id=user.id,
            username=user.username or "",
            display_name=display_name or user.username or str(user.id),
        )

