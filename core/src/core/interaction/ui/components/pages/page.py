from __future__ import annotations

from typing import Optional, Any, Sequence, Dict

from telegram import InlineKeyboardMarkup

from core.interaction.contracts.input_reactive import InputReactive
from core.interaction.input.user_input import UserInput
from core.interaction.ui.components import UiComponent
from core.interaction.ui.builders.keyboard_builder import KeyboardBuilder


class Page(UiComponent, InputReactive):
    """
    Stateless Page.

    Сейчас:
      - умеет рендерить дефолтный keyboard_layout из конфига
      - keyboard_builder прокидывается из UiBuilder

    Следующий шаг (если хочешь менять клавиатуру страницы во время работы):
      - добавить хранение layout в page state (аналог process payload)
      - переопределить _get/_set_keyboard_layout_storage
    """

    def __init__(
        self,
        text_template: str,
        inline_keyboard_template: Optional[InlineKeyboardMarkup] = None,
        *,
        keyboard_builder: Optional[KeyboardBuilder] = None,
        html_escape_variables: bool = False,
        default_keyboard_layout: Optional[Sequence[Sequence[Any]]] = None,
    ) -> None:
        super().__init__(
            text_template=text_template,
            inline_keyboard_template=inline_keyboard_template,
            keyboard_builder=keyboard_builder,
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
        """
        Пока у Page нет своего storage в user_data.
        Поэтому просто отдаём дефолтный layout (если он есть).
        """
        if self._default_keyboard_layout is not None:
            return {"layout": self._default_keyboard_layout}
        return {}