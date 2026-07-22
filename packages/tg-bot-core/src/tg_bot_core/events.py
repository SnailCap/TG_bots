from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


UserRole = Literal["user", "trusted", "moderator", "administrator"]


@dataclass(frozen=True, slots=True)
class Actor:
    user_id: int
    chat_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    role: UserRole = "user"
    language_code: str | None = None


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
    text: str = ""
    kind: Literal["message"] = "message"


@dataclass(frozen=True, slots=True)
class CallbackEvent(InteractionEvent):
    action_id: str = ""
    kind: Literal["callback"] = "callback"


@dataclass(frozen=True, slots=True)
class LifecycleEvent(InteractionEvent):
    hook: str = ""
    kind: Literal["lifecycle"] = "lifecycle"
