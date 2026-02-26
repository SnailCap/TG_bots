from telegram import Bot
from core.src.interaction.adapters.ptb.messenger import PtbMessenger
from core.src.interaction.contracts.messenger import ChatId
from typing import Any, Optional

class PtbNotifier:
    def __init__(self, bot: Bot) -> None:
        self._messenger = PtbMessenger(bot)

    async def notify(self, *, chat_id: ChatId, text: str, reply_markup: Optional[Any]=None,
                     parse_mode: Optional[str]="HTML", **kwargs: Any) -> Any:
        return await self._messenger.send(
            chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode, **kwargs
        )
