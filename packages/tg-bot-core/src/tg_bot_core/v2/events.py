from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class Actor:
    user_id: int
    chat_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None


@dataclass(frozen=True, slots=True)
class InteractionEvent:
    actor: Actor
    update_id: int


@dataclass(frozen=True, slots=True)
class CommandEvent(InteractionEvent):
    command: str
    arguments: str = ""
    kind: Literal["command"] = "command"


@dataclass(frozen=True, slots=True)
class MessageEvent(InteractionEvent):
    text: str
    kind: Literal["message"] = "message"


@dataclass(frozen=True, slots=True)
class CallbackEvent(InteractionEvent):
    action: dict[str, str]
    kind: Literal["callback"] = "callback"


@dataclass(frozen=True, slots=True)
class EnterEvent(InteractionEvent):
    kind: Literal["enter"] = "enter"
