from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Awaitable, Callable, Mapping, Protocol, Sequence, runtime_checkable

from app.domain.project import BotIdentity


class UpdateKind(StrEnum):
    COMMAND = "command"
    MESSAGE = "message"
    CALLBACK = "callback"


class KeyboardKind(StrEnum):
    INLINE = "inline"
    REPLY = "reply"


class MediaKind(StrEnum):
    PHOTO = "photo"
    DOCUMENT = "document"


@dataclass(frozen=True, slots=True)
class IncomingUpdate:
    """Transport-neutral snapshot of one subscriber update."""

    update_id: int
    telegram_user_id: int
    telegram_chat_id: int
    kind: UpdateKind
    text: str | None = None
    callback_data: str | None = None
    command: str | None = None
    message_id: int | None = None
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def is_start(self) -> bool:
        return self.kind is UpdateKind.COMMAND and (self.command or "").casefold() == "start"

    @property
    def input_value(self) -> str | None:
        if self.kind is UpdateKind.CALLBACK:
            return self.callback_data
        return self.text


@dataclass(frozen=True, slots=True)
class KeyboardButton:
    text: str
    value: str | None = None
    url: str | None = None


@dataclass(frozen=True, slots=True)
class Keyboard:
    kind: KeyboardKind
    rows: Sequence[Sequence[KeyboardButton]]
    resize: bool = True
    one_time: bool = False


@dataclass(frozen=True, slots=True)
class OutboundMessage:
    chat_id: int
    text: str | None = None
    parse_mode: str | None = None
    keyboard: Keyboard | None = None
    media_kind: MediaKind | None = None
    media: str | bytes | None = None
    caption: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


UpdateHandler = Callable[[IncomingUpdate], Awaitable[None]]


@runtime_checkable
class TelegramPort(Protocol):
    """Boundary implemented by long-polling today and a worker proxy later."""

    @property
    def is_running(self) -> bool: ...

    async def start(self, handler: UpdateHandler) -> BotIdentity: ...

    async def stop(self) -> None: ...

    async def send(self, message: OutboundMessage) -> Any: ...
