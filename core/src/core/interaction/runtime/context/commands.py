from __future__ import annotations

from enum import Enum

from .callback_protocol import ServiceCallbackData


class BotCommand(str, Enum):
    START_COMMAND = "start"
    HOME_COMMAND = "home"


class ProcessCommand(str, Enum):
    NEXT = "next"
    PREV = "prev"
    CANCEL = "cancel"

    @property
    def callback_data(self) -> str:
        return f"{ServiceCallbackData.PRC_CMD.value}{self.value}"