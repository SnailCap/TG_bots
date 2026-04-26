from __future__ import annotations

from typing import Any, Optional, Dict
from telegram import InlineKeyboardMarkup

from core.interaction.ui.components.base import UiComponent
from core.interaction.ui.keyboard.keyboard_builder import KeyboardBuilder
from core.interaction.ui.templating.text_renderer import TextRenderer


class Notification(UiComponent):
    def __init__(
        self,
        text_template: str,
        inline_keyboard_template: Optional[InlineKeyboardMarkup] = None,
        *,
        keyboard_builder: Optional[KeyboardBuilder] = None,
        text_renderer: TextRenderer,
        default_keyboard_layout: Optional[Any] = None,
        html_escape_variables: bool = False,
        parse_mode: Optional[str] = "HTML",
    ) -> None:
        super().__init__(
            text_template=text_template,
            inline_keyboard_template=inline_keyboard_template,
            keyboard_builder=keyboard_builder,
            text_renderer=text_renderer,
            html_escape_variables=html_escape_variables,
        )
        self._parse_mode = parse_mode
        self._default_keyboard_layout = default_keyboard_layout

    def get_parse_mode(self) -> Optional[str]:
        return self._parse_mode

    async def render_detached(
        self,
        *,
        text_vars: Optional[Dict[str, Any]] = None,
        kb_vars: Optional[Dict[str, Any]] = None,
    ):
        if kb_vars is None and self._default_keyboard_layout is not None:
            kb_vars = {self._LAYOUT_KEY: self._default_keyboard_layout}

        return await super().render_detached(text_vars=text_vars, kb_vars=kb_vars)