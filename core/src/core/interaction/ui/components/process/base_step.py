from __future__ import annotations

from typing import Any, Dict, Optional, Sequence, TYPE_CHECKING

from telegram import InlineKeyboardMarkup

if TYPE_CHECKING:
    from core.interaction.input.user_input import UserInput

from core.interaction.contracts.input_reactive import InputReactive
from ...keyboard import KeyboardBuilder
from .effects import (
    Cancel,
    Finish,
    GoNext,
    GoPrev,
    GoToStep,
    StepResult,
)
from ..base import UiComponent


class Step(UiComponent, InputReactive):
    """
    Stateless Step.

    - Text variables and keyboard layout overrides are stored in the active process payload.
    - Effective keyboard layout:
        1) payload override ("keyboard_layout") if present and not None
        2) default_keyboard_layout provided at construction time (usually from config)
    """

    _PAYLOAD_TEXT_VARS = "text_variables"
    _PAYLOAD_KB_LAYOUT = "keyboard_layout"
    _PAYLOAD_KB_VARS = "keyboard_variables"

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
            text_template,
            inline_keyboard_template,
            keyboard_builder=keyboard_builder,
            html_escape_variables=html_escape_variables,
        )
        self._default_keyboard_layout = default_keyboard_layout

    async def render(self, user_input: UserInput, with_send: bool = False) -> None:
        await self._on_start(user_input)
        await super().render(user_input, with_send=with_send)

    async def _on_start(self, user_input: UserInput) -> None:
        return

    async def handle_input(self, user_input: UserInput) -> StepResult:
        if user_input.is_callback:
            return await self.handle_callback(user_input)
        if user_input.is_message:
            return await self.handle_message(user_input)
        return None

    async def handle_message(self, user_input: UserInput) -> StepResult:
        return None

    async def handle_callback(self, user_input: UserInput) -> StepResult:
        return None

    async def is_input_valid(self, user_input: UserInput) -> bool:
        return True

    # --- navigation helpers ---
    @staticmethod
    def go_next() -> GoNext:
        return GoNext()

    @staticmethod
    def go_prev() -> GoPrev:
        return GoPrev()

    @staticmethod
    def go_to_step(step_name: str) -> GoToStep:
        return GoToStep(step_name)

    @staticmethod
    def finish() -> Finish:
        return Finish()

    @staticmethod
    def cancel() -> Cancel:
        return Cancel()

    # --- state helpers ---
    def _active_proc(self, user_input: UserInput) -> Optional[str]:
        if not user_input.state.has_active_process():
            return None
        try:
            return user_input.state.get_active_process()
        except RuntimeError:
            return None

    def _payload(self, user_input: UserInput) -> dict:
        name = self._active_proc(user_input)
        return user_input.state.get_process_payload(name) if name else {}

    def _patch_payload(self, user_input: UserInput, **kwargs: Any) -> None:
        name = self._active_proc(user_input)
        if name:
            user_input.state.update_process_payload(name, **kwargs)

    def _get_keyboard_layout_storage(self, user_input: UserInput) -> Any:
        return self._payload(user_input).get(self._PAYLOAD_KB_LAYOUT)

    def _set_keyboard_layout_storage(self, user_input: UserInput, value: Any) -> None:
        self._patch_payload(user_input, **{self._PAYLOAD_KB_LAYOUT: value})

    def _get_keyboard_layout_effective(
        self, user_input: UserInput
    ) -> Optional[Sequence[Sequence[Any]]]:
        stored = self._get_keyboard_layout_storage(user_input)
        return stored if stored is not None else self._default_keyboard_layout

    async def _build_text_context(self, user_input: UserInput) -> Dict[str, Any]:
        ctx = await super()._build_text_context(user_input)
        payload_vars = dict(self._payload(user_input).get(self._PAYLOAD_TEXT_VARS, {}) or {})
        ctx.update(payload_vars)
        return ctx

    async def _build_keyboard_context(self, user_input: UserInput) -> Dict[str, Any]:
        ctx = await super()._build_keyboard_context(user_input)

        payload_kb_vars = dict(self._payload(user_input).get(self._PAYLOAD_KB_VARS, {}) or {})
        ctx.update(payload_kb_vars)

        layout = self._get_keyboard_layout_effective(user_input)
        if layout is not None:
            ctx["layout"] = layout

        return ctx