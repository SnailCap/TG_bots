"""Core v2 public API for explicit Telegram bot applications."""

from tg_bot_core.v2.app import BotApp
from tg_bot_core.v2.config import BotConfig, StartPolicy
from tg_bot_core.v2.events import CallbackEvent, CommandEvent, MessageEvent
from tg_bot_core.v2.flows import FlowDefinition, FlowState, Transition
from tg_bot_core.v2.jobs import ScheduleSpec, TaskHandler
from tg_bot_core.v2.module import BotModule, ServiceProvider

__all__ = [
    "BotApp",
    "BotConfig",
    "BotModule",
    "CallbackEvent",
    "CommandEvent",
    "FlowDefinition",
    "FlowState",
    "MessageEvent",
    "ScheduleSpec",
    "ServiceProvider",
    "StartPolicy",
    "TaskHandler",
    "Transition",
]
