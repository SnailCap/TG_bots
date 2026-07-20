from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

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


EventHandler = Callable[[InteractionEvent], Awaitable[None]]


class BotTransport(Protocol):
    async def start(self, handler: EventHandler) -> None: ...
    async def stop(self) -> None: ...
    async def send(self, message: OutboundMessage) -> None: ...
