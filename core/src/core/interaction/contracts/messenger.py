from __future__ import annotations

from typing import Any, Optional, Protocol, TypeAlias, runtime_checkable, Union

ChatId = Union[int, str]

@runtime_checkable
class Messenger(Protocol):
    async def send(
            self,
            *,
            chat_id: ChatId,
            text: str,
            reply_markup: Optional[Any] = None,
            parse_mode: Optional[str] = "HTML",
            **kwargs: Any,
    ) -> Any: ...

    async def edit(
            self,
            *,
            chat_id: ChatId,
            message_id: int,
            text: str,
            reply_markup: Optional[Any] = None,
            parse_mode: Optional[str] = "HTML",
            **kwargs: Any,
    ) -> Any: ...

    async def send_or_edit(
            self,
            *,
            chat_id: ChatId,
            text: str,
            reply_markup: Optional[Any] = None,
            parse_mode: Optional[str] = "HTML",
            message_id: Optional[int] = None,
            **kwargs: Any,
    ) -> Any: ...
