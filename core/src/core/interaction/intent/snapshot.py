from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from telegram import Update

from core.interaction.types import UserInputType


@dataclass(frozen=True, slots=True)
class InputSnapshot:
    """
    Immutable, minimal snapshot of what the user sent.

    Intentionally does not know about svc:* semantics and does not send messages.
    """
    type: UserInputType
    text: Optional[str] = None
    callback_data: Optional[str] = None

    @property
    def is_command(self) -> bool:
        return self.type == UserInputType.COMMAND

    @property
    def is_callback(self) -> bool:
        return self.type == UserInputType.CALLBACK

    @property
    def is_message(self) -> bool:
        return self.type == UserInputType.MESSAGE

    @property
    def callback(self) -> str:
        return self.callback_data or ""

    @property
    def command(self) -> Optional[str]:
        return self.text if self.is_command else None

    @property
    def with_send_default(self) -> bool:
        # CALLBACK -> edit; MESSAGE/COMMAND -> send
        return not self.is_callback

    @staticmethod
    def from_update(update: Update) -> "InputSnapshot":
        if update.callback_query is not None:
            return InputSnapshot(
                type=UserInputType.CALLBACK,
                callback_data=update.callback_query.data or "",
                text=None,
            )

        if update.message is not None:
            raw_text = update.message.text
            if not raw_text:
                return InputSnapshot(type=UserInputType.MESSAGE, text=None, callback_data=None)

            if raw_text.startswith("/"):
                return InputSnapshot(type=UserInputType.COMMAND, text=raw_text[1:], callback_data=None)

            return InputSnapshot(type=UserInputType.MESSAGE, text=raw_text, callback_data=None)

        return InputSnapshot(type=UserInputType.UNKNOWN, text=None, callback_data=None)