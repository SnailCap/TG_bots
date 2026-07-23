from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .events import InteractionEvent


@dataclass(frozen=True, slots=True)
class OutboundButton:
    text: str
    callback_data: str


@dataclass(frozen=True, slots=True)
class OutboundMessage:
    chat_id: int
    text: str
    keyboard: tuple[tuple[OutboundButton, ...], ...] = ()
    edit_message_id: int | None = None


@dataclass(frozen=True, slots=True)
class UserProfileAvatar:
    """Latest Telegram profile photo, or an explicit absence of one."""

    file_id: str | None
    data: bytes | None = None
    mime_type: str | None = None


EventHandler = Callable[[InteractionEvent], Awaitable[None]]


class BotTransport(Protocol):
    async def start(self, handler: EventHandler) -> None: ...
    async def stop(self) -> None: ...
    async def send(self, message: OutboundMessage) -> None: ...


@runtime_checkable
class UserProfileProvider(Protocol):
    """Optional transport capability used by the durable user registry."""

    async def fetch_user_avatar(
        self, user_id: int, current_file_id: str | None
    ) -> UserProfileAvatar: ...
