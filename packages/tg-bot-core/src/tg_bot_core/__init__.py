"""Public SDK and runtime for declarative Telegram Bot Studio projects."""

from .app import BotApp
from .config import BotConfig
from .content import TelegramMessageEntity
from .events import Actor, CallbackEvent, CommandEvent, MessageEvent
from .sdk import (
    BaseHandlerContext,
    ButtonContext,
    ChatInfo,
    CommandContext,
    HandlerResult,
    LifecycleContext,
    MessageContext,
    StateValues,
    TaskContext,
    UserInfo,
)
from .services import ServiceProvider
from .transport import BotTransport, OutboundButton, OutboundMessage

__version__ = "3.0.0"

__all__ = [
    "Actor",
    "BaseHandlerContext",
    "BotApp",
    "BotConfig",
    "BotTransport",
    "ButtonContext",
    "CallbackEvent",
    "ChatInfo",
    "CommandContext",
    "CommandEvent",
    "HandlerResult",
    "LifecycleContext",
    "MessageContext",
    "MessageEvent",
    "OutboundButton",
    "OutboundMessage",
    "ServiceProvider",
    "StateValues",
    "TaskContext",
    "TelegramMessageEntity",
    "UserInfo",
]
