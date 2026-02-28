from __future__ import annotations
from typing import Optional
from telegram import InlineKeyboardMarkup

from core.interaction.ui.components import UiComponent


class Notification(UiComponent):
    def __init__(
            self,
            text_template: str,
            inline_keyboard_template: Optional[InlineKeyboardMarkup] = None,
            html_escape_variables: bool = False,
            parse_mode: Optional[str] = "HTML",
    ):
        super().__init__(
            text_template=text_template,
            inline_keyboard_template=inline_keyboard_template,
            html_escape_variables=html_escape_variables,
        )
        self._parse_mode = parse_mode
