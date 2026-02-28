# core/src/interaction/types/process_commands.py
from __future__ import annotations
from enum import Enum

from core.interaction.types.callback_data import ServiceCallbackData


class ProcessCommand(str, Enum):
    NEXT = "next"
    PREV = "prev"
    CANCEL = "cancel"

    @property
    def callback_data(self) -> str:
        return f"{ServiceCallbackData.PRC_CMD.value}{self.value}"