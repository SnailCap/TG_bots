from __future__ import annotations

from typing import Optional, Any, Sequence, Dict, TYPE_CHECKING

from telegram import InlineKeyboardMarkup

from core.interaction.ui.templating.text_renderer import TextRenderer

if TYPE_CHECKING:
    from core.interaction.runtime.context.user_input import UserInput
from core.interaction.contracts.input_reactive import InputReactive
from core.interaction.ui.components.base import UiComponent
from core.interaction.ui.keyboard.keyboard_builder import KeyboardBuilder


class Page(UiComponent, InputReactive):
    def __init__(
        self,
        text_template: str,
        inline_keyboard_template: Optional[InlineKeyboardMarkup] = None,
        *,
        keyboard_builder: Optional[KeyboardBuilder] = None,
        text_renderer: TextRenderer,
        html_escape_variables: bool = False,
        default_keyboard_layout: Optional[Sequence[Sequence[Any]]] = None,
    ) -> None:
        super().__init__(
            text_template=text_template,
            inline_keyboard_template=inline_keyboard_template,
            keyboard_builder=keyboard_builder,
            text_renderer=text_renderer,
            html_escape_variables=html_escape_variables,
        )
        self._default_keyboard_layout = default_keyboard_layout

    async def is_input_valid(self, user_input: UserInput) -> bool:
        return True

    async def handle_message(self, user_input: UserInput) -> None:
        await self.render(user_input)

    async def handle_callback(self, user_input: UserInput) -> None:
        await self.render(user_input)

    async def _build_keyboard_context(self, user_input: UserInput) -> Dict[str, Any]:
        ctx = await super()._build_keyboard_context(user_input)
        if "layout" not in ctx and self._default_keyboard_layout is not None:
            ctx["layout"] = self._default_keyboard_layout
        return ctx