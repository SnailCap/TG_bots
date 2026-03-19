from __future__ import annotations

from html import escape as html_escape
from typing import TYPE_CHECKING, Optional, Dict, Any, Tuple, Final

from telegram import InlineKeyboardMarkup

from core.interaction.exceptions.template_errors import PlaceholderFormatError
from core.interaction.types import TemplateContext
from core.interaction.ui.keyboard.keyboard_builder import KeyboardBuilder
from core.interaction.ui.templating.keyboard import format_inline_keyboard

if TYPE_CHECKING:
    from core.interaction.runtime.user_input import UserInput


class UiComponent:
    """
    Stateless UI component.

    Keyboard rendering strategy:
      1) If the keyboard context contains {"layout": ...} -> build via KeyboardBuilder
      2) Else -> legacy template formatting via format_inline_keyboard(inline_keyboard_template, kb_vars)
    """

    _LAYOUT_KEY: Final[str] = "layout"

    def __init__(
        self,
        text_template: str,
        inline_keyboard_template: Optional[InlineKeyboardMarkup],
        *,
        keyboard_builder: Optional[KeyboardBuilder] = None,
        html_escape_variables: bool = False,
    ) -> None:
        self._text_template: Final[str] = text_template
        self._inline_keyboard_template: Final[Optional[InlineKeyboardMarkup]] = inline_keyboard_template
        self._keyboard_builder: Final[Optional[KeyboardBuilder]] = keyboard_builder
        self._html_escape: Final[bool] = html_escape_variables

    async def render(self, user_input: "UserInput", with_send: bool = False) -> None:
        text = await self.get_text(user_input)
        keyboard = await self.get_inline_keyboard(user_input)
        await user_input.reply(text, keyboard, with_send=with_send)

    async def get_text(
        self,
        user_input: Optional["UserInput"],
        *,
        text_vars: Optional[Dict[str, Any]] = None,
    ) -> str:
        if text_vars is not None:
            vars_: Dict[str, Any] = text_vars
        elif user_input is not None:
            vars_ = await self._build_text_context(user_input)
        else:
            vars_ = {}
        return self.__insert_text_variables(vars_)

    async def get_inline_keyboard(
        self,
        user_input: Optional["UserInput"],
        *,
        kb_vars: Optional[Dict[str, Any]] = None,
    ) -> Optional[InlineKeyboardMarkup]:
        if kb_vars is not None:
            kb_ctx: Dict[str, Any] = kb_vars
        elif user_input is not None:
            kb_ctx = await self._build_keyboard_context(user_input)
        else:
            kb_ctx = {}

        # New path: layout-based keyboard (keys / ButtonRef / dicts)
        layout = None
        if isinstance(kb_ctx, dict):
            layout = kb_ctx.get(self._LAYOUT_KEY)

        if layout is not None:
            if self._keyboard_builder is None:
                raise RuntimeError(
                    "Keyboard layout was provided, but UiComponent has no KeyboardBuilder. "
                    "Pass keyboard_builder=... when constructing UiComponent/Step/Page."
                )
            return self._keyboard_builder.build_optional(layout)

        # Legacy path: InlineKeyboardMarkup template + format vars
        return format_inline_keyboard(
            self._inline_keyboard_template,
            kb_ctx,
            html_escape_variables=self._html_escape,
        )

    def get_inline_keyboard_template(self) -> Optional[InlineKeyboardMarkup]:
        return self._inline_keyboard_template

    def get_text_template(self) -> str:
        return self._text_template

    async def _provide_context(self, user_input: "UserInput", ctx: TemplateContext) -> None:
        return

    async def _build_text_context(self, user_input: "UserInput") -> Dict[str, Any]:
        ctx = TemplateContext()
        await self._provide_context(user_input, ctx)
        return ctx.text

    async def _build_keyboard_context(self, user_input: "UserInput") -> Dict[str, Any]:
        ctx = TemplateContext()
        await self._provide_context(user_input, ctx)
        return ctx.keyboard

    def __insert_text_variables(self, variables: Dict[str, Any]) -> str:
        try:
            if self._html_escape and variables:
                safe_vars = {k: (html_escape(v) if isinstance(v, str) else v) for k, v in variables.items()}
                return self._text_template.format(**safe_vars)

            return self._text_template.format(**variables) if variables else self._text_template
        except Exception as e:
            raise PlaceholderFormatError(self._text_template, variables, e)

    async def render_detached(
        self,
        *,
        text_vars: Optional[Dict[str, Any]] = None,
        kb_vars: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
        text = await self.get_text(None, text_vars=text_vars)
        kb = await self.get_inline_keyboard(None, kb_vars=kb_vars)
        return text, kb

    async def to_out_params(
        self,
        *,
        chat_id: int,
        message_id: Optional[int] = None,
        text_vars: Optional[Dict[str, Any]] = None,
        kb_vars: Optional[Dict[str, Any]] = None,
        parse_mode: Optional[str] = None,
        **extra: Any,
    ) -> Dict[str, Any]:
        text, kb = await self.render_detached(text_vars=text_vars, kb_vars=kb_vars)

        out: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "reply_markup": kb,
        }
        if parse_mode is not None:
            out["parse_mode"] = parse_mode
        if message_id is not None:
            out["message_id"] = message_id
        if extra:
            out.update(extra)
        return out