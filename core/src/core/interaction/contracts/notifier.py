from typing import Protocol, Any, Optional
from core.interaction.contracts.messenger import ChatId

class Notifier(Protocol):
    async def notify(
        self,
        *,
        chat_id: ChatId,
        text: str,
        reply_markup: Optional[Any] = None,
        parse_mode: Optional[str] = "HTML",
        **kwargs: Any,
    ) -> Any: ...
